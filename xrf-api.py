


#!flask/bin/python
from flask import Flask, jsonify
from flask import abort
from flask import make_response
import xrf


# Create web API instance.
app = Flask(__name__)

# Start the Xi-Fi interface
xrfAPI = xrf.XrfAPI()
xrfAPI.start()


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.route('/xrf-api/v1.0/devices', methods=['GET'])
def get_devices():
    devices = xrfAPI.getDevices()
    return jsonify({'devices': devices})


@app.route('/xrf-api/v1.0/device/<uid>', methods=['GET'])
def get_device(uid):
    devices = xrfAPI.getDevices()
    device = [device for device in devices if device['uid'] == uid]
    if len(device) == 0:
        abort(404)
    return jsonify({'device': device[0]})


@app.route('/xrf-api/v1.0/enumerate/<int:channel>', methods=['GET'])
def enumerate_devices(channel):
    xrfAPI.setChannel(channel)
    xrfAPI.IDRequestAll(0xFF)
    devices = xrfAPI.getDevices()
    return jsonify({'devices': devices})


@app.route('/xrf-api/v1.0/info', methods=['GET'])
def get_info():
    devices = dict()
    device1 = dict()
    device1['foo'] = 'bar'
    device1['bar'] = 'foo'
    devices['device1'] = device1
    device = devices['device1']
    if device:
        device['newkey'] = 'newvalue'
    return jsonify({'devices': devices})


if __name__ == '__main__':
    app.run(debug=True)


