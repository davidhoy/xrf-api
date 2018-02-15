# -*- coding: utf-8 -*-
"""
XRF Protocol Driver
"""
from __future__ import print_function

import Queue
import logging
import threading
import time
import serial
import serial.tools.list_ports


logging.basicConfig(level=logging.DEBUG, format='(%(asctime)-15s %(threadName)-10s) %(message)s')

XRF_VERSION = 2     # version of XRF specification to be used
XRF_MAXLEN = 61     # maximum total packet length (limited by CC430)
XRF_HOPS = 5        # max number of hops

# xrf packet header bits
XRF_UNICAST = 0x80
XRF_TYPE_MASK = 0x70
XRF_TYPE_SHIFT = 4
XRF_PARAM_SHIFT = 0x0F

# xrf packet types
XRF_TYPE_ID = 0         # request for identification and capabilities
XRF_TYPE_IDACK = 1      # ack with UID and capabilities
XRF_TYPE_GET = 2        # request to get a parameter
XRF_TYPE_GETACK = 3     # ack with a parameter value
XRF_TYPE_SET = 4        # set a parameter
XRF_TYPE_SETACK = 5     # ack with a parameter value
XRF_TYPE_REPORT = 6     # parameter is being reported (asynchronously)
XRF_TYPE_REPORTACK = 7  # parameter is being reported (asynchronously) with UID appended
XRF_TYPE_ACKBIT = 1     # ack bit mask of type

# xrf packet parameters
XRF_PARAM_MOTIONSIMPLE = 0  # motion - simple
XRF_PARAM_MOTIONFANCY = 1   # motion - fancy
XRF_PARAM_LIGHT = 2         # ambient light measurement
XRF_PARAM_TEMP = 3          # temperatures
XRF_PARAM_PWRSTAT = 4       # power status
XRF_PARAM_IPWM = 5          # instantaneous pwm levels (v2)
XRF_PARAM_PWM = 5           # legacy pwm levels (v1)
XRF_PARAM_IPWMD = 6         # instantaneous pwm levels (depreciated)
XRF_PARAM_SWITCH = 7        # switch contact closures
XRF_PARAM_MOTIONTIME = 8    # motion timeout
XRF_PARAM_SELFTEST = 9      # self test
XRF_PARAM_GROUP = 10        # group/channel
XRF_PARAM_SVC_TIMES = 11    # total service times
XRF_PARAM_FADER = 12        # fader
XRF_PARAM_LOCALEN = 13      # local enables
XRF_PARAM_REPORTEN = 14     # report enables
XRF_PARAM_EXTENDED = 15     # extended parameter

# extended parameters
XRF_X_BBDIM_EN = 0          # enable blackbody dimming
XRF_X_CT = 1                # color temperatures (degrees K)
XRF_X_LIGHTLEVELS = 2       # light level triggers
XRF_X_TEMPLEVELS = 3        # temperature trip points
XRF_X_BEEP = 4              # beeper
XRF_X_RELAY = 5             # relay control
XRF_X_UNOCC_DIM = 6         # unoccupied dim level
XRF_X_MINMAX_PWM = 7        # min/max PWM levels for dim
XRF_X_NBATT_DIM = 8         # on battery dim levels (occupied, unocc)
XRF_X_MINMAX_FADER = 9      # min/max dim level for fader
XRF_X_RTC_TIME = 10         # Real Time Clock (RTC) current time (set/get)
XRF_X_RTC_ON = 11           # RTC on (enable) time
XRF_X_RTC_OFF = 12          # RTC off (disable) time
XRF_X_PROD_STR = 13         # product description string (read-only)
XRF_X_HOPCNT = 14           # hop count (for packet origination)
XRF_X_FADETIMES = 15        # fade times (up/down)
XRF_X_REPORTTIME = 16       # report time (seconds)
XRF_X_HWSWITCHES = 17       # hardware switch settings
XRF_X_DALI = 18             # DALI payload
XRF_X_DALI_DIMPACKET = 19   # set up a dim packet to output with pwm changes
XRF_X_I2C = 20              # I2C payload
XRF_X_FW_VER = 21           # firmware version (image 0/1/current)
XRF_X_FW_SIZE = 22          # firmware image N size
XRF_X_FW_CRC = 23           # firmware image CRC/valid
XRF_X_FW_SECT_SIZE = 24     # firmware sector size (must fit into one packet)
XRF_X_FW_SECT_DATA = 25     # firmware image N sector M data
XRF_X_FW_BOOT = 26          # firmware boot command - update with image N & reboot
XRF_X_LOGLEVEL = 27         # remotely set logging level for the fixture
XRF_X_PWRFAIL_SW = 28       # what to do when power fails (for battery fixtures)
XRF_X_PRODUCT_ID = 29       # model number (product ID).
XRF_X_STACKTUNE = 30        # XRF stack tuning
XRF_X_PWMAVG = 31           # long term PWM averages

# local enables
XRF_LOCAL_MOTIONDIM = (1 << 0)
XRF_LOCAL_LIGHT = (1 << 1)
XRF_LOCAL_FADER = (1 << 2)
XRF_LOCAL_TEMP = (1 << 3)
XRF_LOCAL_OCCSWMODE0 = (1 << 4)
XRF_LOCAL_OCCSWMODE1 = (1 << 5)
XRF_LOCAL_CALENDAR = (1 << 6)
XRF_LOCAL_TIMESLAVE = (1 << 7)
XRF_LOCAL_DALIPWM = (1 << 8)

# report enables
XRF_RPT_MOTIONSIMPLE = (1 << 0)
XRF_RPT_MOTION = (1 << 1)
XRF_RPT_LIGHT = (1 << 2)
XRF_RPT_TEMP = (1 << 3)
XRF_RPT_PWRSTAT = (1 << 4)
XRF_RPT_TIMEMASTER = (1 << 5)
XRF_RPT_IPWM = (1 << 6)
XRF_RPT_FADER = (1 << 7)
XRF_RPT_MOTIONTIME = (1 << 8)
XRF_RPT_SELFTEST = (1 << 9)
XRF_RPT_SWITCH = (1 << 12)
XRF_RPT_UID = (1 << 14)

# self test bits
XRF_TEST_START = (1 << 7)
XRF_TEST_RF = (1 << 2)
XRF_TEST_BATTERY = (1 << 1)
XRF_TEST_RELAY = 1

# relay bits
XRF_RELAY_ONOFF	= 1
XRF_RELAY_MODE_DIMOFF = 2	    # if set then dim[1]=0 turns off relay

# switch bits
XRF_SWITCH_VACANCY = 1

#XRF_X_STACKTUNE_DEFAULT = (0x01 << XRF_X_STACKTUNE_POWER_SHFT)

# other stuff
XRF_UNIVERSAL_GROUP = 0xFF      # universal group (all units RX)

# radio states
XRF_IDLE = 0
XRF_RECEIVING = 1
XRF_TRANSMITTING = 2
XRF_TESTMODE = 3
XRF_SLEEP = 4

# UART message types
UMSG_RXPKT = 'R'
UMSG_TXPKT = 'T'
UMSG_CMD = 'C'
UMSG_LOG = 'L'
UMSG_ACK = 0x20

# dongle commands
UCMD_INFO = 0           # send back info string (log)
UCMD_UID = 1            # send back UID string (log)
UCMD_CHANNEL = 2        # change RF channel (stairwell #)
UCMD_ENMESH = 3         # enable meshing by dongle (otherwise it's a passive listener/TX)
UCMD_ENRX = 4           # enable sending RX packets back to host via USB
UCMD_ENRPT = 5          # enable dongle TXing reports via RF (so other devices can sense it on the network)
UCMD_LOGLEVEL = 6       # set log level
UCMD_TESTMODE = 7       # set radio for test mode (CW for power calibration)

# Thread states
UMSGST_IDLE = 0
UMSGST_LEN = 1
UMSGST_DATA = 2



class XrfPacket(object):
    """ Create XRF packet """
    length = 0
    header = 0
    hop = 0
    payload = []

    def __init__(self):
        pass


def IsUnicastToMe(pkt):
    """ Is this a unitcast packet being sent to the current device ID? """
    if pkt.xrf.header & XRF_UNICAST:
        # if(*(uint64*)&(packet->xrf.payload[0]) == ByteOrder::swapIfLittleEndian(deviceUID))
        #    return pdFALSE;
        return True
    return False


class CommandPacket(object):
    """ Create command packet """
    cmd = 0
    xrf_packet = 0

    def __init__(self):
        pass


class UartPacket(object):
    """ Create UART packet """
    type = 0
    length = 0
    payload = None

    def __init__(self):
        pass


def get_serial_port():
    """ Get name of the serial port device to use """
    comports = serial.tools.list_ports.comports()
    for port in comports:
        if port.hwid.startswith('USB VID:PID=10C4:EA60 SER=0001 LOCATION=1-'):
            return port.device
    return None


class XrfCommsThread(threading.Thread):
    """ XRF Protocol Thread """
    defaultHops = 0
    channel = 0

    # Here will be the instance stored.
    __instance = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if XrfCommsThread.__instance == None:
            XrfCommsThread()
        return XrfCommsThread.__instance

    def __init__(self, group=None, target=None, name="XrfComms",
                 args=(), kwargs=None, verbose=None):
        """ Constructor for XrfCommsThread object """
        if XrfCommsThread.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            XrfCommsThread.__instance = self

        threading.Thread.__init__(self, group=group, target=target, name=name,
                                  verbose=verbose)
        self.args = args
        self.kwargs = kwargs
        self.txQueue = Queue.Queue()
        self.rxQueue = Queue.Queue()
        self.state = XRF_IDLE
        self.rxPkt = None

        port = get_serial_port()
        if port:
            logging.debug('opening serial port %s', port)
            self.serial = serial.Serial(port, 115200, timeout=0.1)
        else:
            logging.error('no Xi-Fi dongle detected')
            assert port != None
        return

    def transmit_packet(self, pkt):
        """ Transmit an XRF TX command to the dongle """
        assert pkt.__class__.__name__ == 'UartPacket'
        buff = bytearray([pkt.type, pkt.length])
        buff += pkt.payload
        #debugstr = "".join("%02x " % b for b in buff)
        #logging.debug(' TX: len=%d, %s' % (len(buff), debugStr))
        self.serial.write(buff)
        return

    def new_packet(self, pkt_type):
        """ Create new packet """
        pkt = UartPacket()
        pkt.type = pkt_type
        pkt.length = 0
        pkt.payload = bytearray()
        return pkt

    def parse_buff(self, buff):
        """ Parse an incoming serial buffer for XRF dongle responses """
        count = len(buff)
        for i in range(count):
            ch = buff[i]
            if self.state == UMSGST_IDLE:
                if (ch == UMSG_RXPKT) or (ch == UMSG_TXPKT) or (ch == UMSG_CMD) or (ch == UMSG_LOG):
                    self.rxPkt = self.new_packet(ch)
                    self.state = UMSGST_LEN

            elif self.state == UMSGST_LEN:
                self.rxPkt.length = ord(ch)
                self.state = UMSGST_DATA

            elif self.state == UMSGST_DATA:
                self.rxPkt.payload.append(ch)
                if len(self.rxPkt.payload) >= self.rxPkt.length - 2:
                    self.rxQueue.put(self.rxPkt)
                    self.state = UMSGST_IDLE
            else:
                logging.debug('Invalid state')
        return

    def run(self):
        logging.debug('running with %s and %s', self.args, self.kwargs)
        # pdb.set_trace()

        while True:
            while self.serial.inWaiting() > 0:
                try:
                    buff = self.serial.read(256)
                    #logging.debug('RX:%s', buff.encode('hex'))
                    self.parse_buff(buff)
                except:
                    pass

            while not self.txQueue.empty():
                pkt = self.txQueue.get()
                self.transmit_packet(pkt)
                if not self.txQueue.empty():
                    time.sleep(0.1)         # short time delay if we're going to send multiple packets

        logging.debug('exiting thread')
        return

    def setHopCount(self, hops):
        self.defaultHops = hops
        return

    def dongleGetUID(self):
        buff = bytearray([UCMD_UID])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def dongleGetInfo(self):
        """ Request info from the dongle """
        buff = bytearray([UCMD_INFO])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def dongleSetChannel(self, channel):
        """ Set the radio channel (stairwell #) on the dongle """
        buff = bytearray([UCMD_CHANNEL, channel])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        self.channel = channel
        return

    def dongleEnableRX(self, enableRX):
        """ Enable sending RX packets back to host via the dongle """
        buff = bytearray([UCMD_ENRX, enableRX])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def dongleEnableMesh(self, enableMesh):
        """ Enable meshing on the dongle (otherwise it's a passive listener) """
        buff = bytearray([UCMD_ENMESH, enableMesh])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def dongleEnableReport(self, enableReport):
        """ Enable dongle TXing reports via RF (so other devices can sense it on the network) """
        buff = bytearray([UCMD_ENRPT, enableReport])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def dongleSetLogLevel(self, logLevel):
        """ Set log level on the dongle """
        buff = bytearray([UCMD_LOGLEVEL, logLevel])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def dongleTestMode(self, testMode):
        """ Set dongle's radio to test mode (CW for power calibration) """
        buff = bytearray([UCMD_TESTMODE, testMode])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_CMD
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def rfIDRequestAll(self, group):
        """ Request ID from all devices on current channel and specified group """
        pkttype = XRF_TYPE_ID
        unicast = 0
        param = 0
        header = pkttype << XRF_TYPE_SHIFT
        header |= param & XRF_PARAM_SHIFT
        header |= unicast << 7
        hops = self.defaultHops
        buff = bytearray([3, header, hops, group])
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_TXPKT
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def rfGetParameter(self, param, group, uid):
        """ Request specified parameter from group of specific fixture """
        pkttype = XRF_TYPE_GET
        unicast = 0
        if uid != None:
            unicast = 1
        header = pkttype << XRF_TYPE_SHIFT
        header |= param & XRF_PARAM_SHIFT
        header |= unicast << 7
        hops = self.defaultHops
        buff = bytearray([0, header, hops])
        if uid != None:
            buff += uid
        else:
            buff += chr(group)
        buff[0] = len(buff) - 1
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_TXPKT
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def rfSetParameter(self, param, group, uid, values):
        """ Set parameter(s) on group or specified fixture """
        pkttype = XRF_TYPE_SET
        unicast = 0
        if uid != None:
            unicast = 1
        header = pkttype << XRF_TYPE_SHIFT
        header |= param & XRF_PARAM_SHIFT
        header |= unicast << 7
        hops = self.defaultHops
        buff = bytearray([0, header, hops])
        if uid != None:
            buff += uid
        else:
            buff += chr(group)
        if values != None:
            buff += values
        buff[0] = len(buff) - 1
        uart_pkt = UartPacket()
        uart_pkt.type = UMSG_TXPKT
        uart_pkt.length = len(buff) + 2
        uart_pkt.payload = buff
        self.txQueue.put(uart_pkt)
        return

    def rfSetPWMLevel(self, group, uid, pwmLevels):
        """ Set PWM levels on group or specified fixture """
        self.rfSetParameter(XRF_PARAM_IPWM, group, uid, pwmLevels)
        return

    def rfGetPWMLevel(self, group, uid):
        """ Get PWN levels from group or specified fixture """
        self.rfGetParameter(XRF_PARAM_IPWM, group, uid)
        return


class XrfAPI(threading.Thread):
    """ XRF API class """
    # Here will be the instance stored.
    __instance = None
    discoveredDevices = None
    deviceLock = None
    currentChannel = 1


    @staticmethod
    def getInstance():
        """ Static access method. """
        if XrfAPI.__instance == None:
            XrfAPI()
        return XrfAPI.__instance

    def __init__(self, group=None, target=None, name="XrfAPI",
                 args=(), kwargs=None, verbose=None):
        """ Constructor for XrfAPI object """
        if XrfAPI.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            XrfAPI.__instance = self

        threading.Thread.__init__(self, group=group, target=target, name=name,
                                  verbose=verbose)
        self.args = args
        self.xrfThread = XrfCommsThread.getInstance()
        self.xrfThread.start()
        self.discoveredDevices = dict()
        self.deviceLock = threading.Lock()
        self.currentChannel = 1
        return

    def run(self):
        """ Main thread for XrfAPI """
        while True:
            if not self.xrfThread.rxQueue.empty():
                pkt = self.xrfThread.rxQueue.get()
                #debugStr = 'RX packet: '.join('%02x ' % b for b in pkt.payload)
                #print(debugStr)
                if pkt.type == 'L':
                    #print('Log message')
                    try:
                        dbgstr = pkt.payload.decode('ascii')
                        dbgstr = dbgstr.rstrip('\r\n')
                        #logging.debug('DBG: ' + dbgstr)
                    except:
                        pass
                elif pkt.type == 'R':
                    self.parseRxPacket(pkt.payload)
                elif pkt.type == 'T':
                    debugStr = ''.join('%02x' % b for b in pkt.payload)
                    print('TX packet ' + debugStr)
                elif pkt.type == 'C':
                    debugStr = ''.join('%02x' % b for b in pkt.payload)
                    print('Dongle command ' + debugStr)
                else:
                    print('unknown type %c' % pkt.type)
        return

    def typeToName(self, type):
        """ Convert message type to a string """
        if type == XRF_TYPE_ID:
            return 'ID Request'
        elif type == XRF_TYPE_IDACK:
            return 'ID Ack'
        elif type == XRF_TYPE_GET:
            return 'Get Param'
        elif type == XRF_TYPE_GETACK:
            return 'Get Ack'
        elif type == XRF_TYPE_SET:
            return 'Set Param'
        elif type == XRF_TYPE_SETACK:
            return 'Set Ack'
        elif type == XRF_TYPE_REPORT:
            return 'Report Param'
        elif type == XRF_TYPE_REPORTACK:
            return 'Report Ack'
        return str(type)

    def paramToName(self, param):
        """ Convert parameter type to a string """
        if param == XRF_PARAM_MOTIONSIMPLE:
            return "Motion Simple"
        elif param == XRF_PARAM_MOTIONFANCY:
            return "Motion Fancy"
        elif param == XRF_PARAM_LIGHT:
            return "Ambient Light Level"
        elif param == XRF_PARAM_TEMP:
            return "Temperature"
        elif param == XRF_PARAM_PWRSTAT:
            return "Power Status"
        elif param == XRF_PARAM_PWM:
            return "PWM Levels"
        elif param == XRF_PARAM_IPWMD:
            return "Instantaneous PWM"
        elif param == XRF_PARAM_SWITCH:
            return "Switch Closures"
        elif param == XRF_PARAM_MOTIONTIME:
            return "Motion Timeout"
        elif param == XRF_PARAM_SELFTEST:
            return "Self Test"
        elif param == XRF_PARAM_GROUP:
            return "Group/channel"
        elif param == XRF_PARAM_SVC_TIMES:
            return "Operating Lifetime Info"
        elif param == XRF_PARAM_FADER:
            return "Fader"
        elif param == XRF_PARAM_LOCALEN:
            return "Mode Enables"
        elif param == XRF_PARAM_REPORTEN:
            return "Report Enables"
        elif param == XRF_PARAM_EXTENDED:
            return "Extended Parameter"
        return str(param)

    def modelToString(self, model):
        """ Convert model number to a string """
        if model == 0:
            return "Athena"
        elif model == 1:
            return "AthenaX"
        elif model == 2:
            return "Artemis"
        elif model == 4:
            return "Artemis XL"
        elif model == 6:
            return "USB Dongle"
        return str(model)

    def parseRxPacket(self, payload):
        """ Parse a received packet, updating the device database as necessary """
        #debugStr = "".join("%02x " % b for b in payload)
        #logging.debug(debugStr)
        length = payload[0]
        msgheader = payload[1]
        unicast = msgheader | 0x80
        msgtype = (msgheader & 0x70) >> 4
        msgparam = (msgheader & 0x0F)
        hopcount = payload[2]
        group = payload[3]
        typename = self.typeToName(msgtype)
        paramName = self.paramToName(msgparam)
        logging.debug('RX: type=%s, param=%s, hop=%d, group=%d' % (typename, paramName, hopcount, group))

        self.deviceLock.acquire()
        #print(self)
        #print('Before:' + str(self.discoveredDevices))

        if msgtype == XRF_TYPE_ID:
            logging.debug('XRF_TYPE_ID')

        elif msgtype == XRF_TYPE_IDACK:
            #logging.debug('XRF_TYPE_IDACK')
            uid = bytearray([payload[4], payload[5], payload[6], payload[7], payload[8], payload[9], payload[10], payload[11]])
            uidStr = "".join("%02x" % b for b in uid)
            model = payload[13]
            modelStr = self.modelToString(model)
            version = payload[12] * 10

            device = self.discoveredDevices.get(uidStr)
            if not device:
                logging.debug('Discovered new device ' + uidStr)
                device = dict()
                self.discoveredDevices[uidStr] = device
            else:
                logging.debug('Discovered existing device ' + uidStr)
            device['model'] = modelStr
            device['group'] = group
            device['hopcount'] = hopcount
            device['channel'] = self.currentChannel
            device['fwversion'] = version

        elif msgtype == XRF_TYPE_REPORTACK:
            #logging.debug('XRF_TYPE_REPORTACK')
            uid = bytearray([payload[4], payload[5], payload[6], payload[7], payload[8], payload[9], payload[10], payload[11]])
            uidStr = "".join("%02x" % b for b in uid)

            # Get/create device object
            device = self.discoveredDevices.get(uidStr)
            if not device:
                logging.debug('Discovered new device ' + uidStr)
                device = dict()
                self.discoveredDevices[uidStr] = device
            else:
                logging.debug('Discovered existing device ' + uidStr)

            device['group'] = group
            device['hopcount'] = hopcount

            if msgparam == XRF_PARAM_MOTIONSIMPLE:
                timestamp = time.ctime()
                device['lastmotion'] = timestamp
                device['lastmotiontype'] = 'simple'

            elif msgparam == XRF_PARAM_MOTIONFANCY:
                timestamp = time.ctime()
                device['lastmotion'] = timestamp
                device['lastmotiontype'] = 'fancy'
        else:
            logging.debug('Unsupported (yet!) msg type %d (%s)' % (msgtype, typename))

        #print(' After:' + str(self.discoveredDevices))
        self.deviceLock.release()
        return

    def setChannel(self, channel):
        """ Set the radio channel """
        self.currentChannel = channel
        self.xrfThread.dongleSetChannel(channel)
        return

    def IDRequestAll(self, group):
        """ Send an ID request to the specified group (or wildcard) """
        self.xrfThread.rfIDRequestAll(group)
        time.sleep(5)
        device_list = self.getDevices()
        return device_list

    def getDevices(self):
        """ Convert discoveredDevices dictionary into a list """
        #print(self)
        #print(dir(self))
        device_list = list()
        self.deviceLock.acquire()
        #print(str(self.discoveredDevices))
        keys = self.discoveredDevices.keys()
        for uidStr in keys:
            device = self.discoveredDevices.get(uidStr)
            new_device = dict()
            new_device['uid'] = uidStr
            for key in device.keys():
                new_device[key] = device[key]
            device_list.append(new_device)
        self.deviceLock.release()
        return device_list
