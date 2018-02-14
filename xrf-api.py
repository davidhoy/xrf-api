#!flask/bin/python

from flask import Flask, jsonify
from flask import abort
from flask import make_response
from flask import url_for
from xrf import XrfAPI

# Create web API instance.
app = Flask(__name__)
port = 5000


def make_public_device(device):
    new_device = dict()
    for field in device:
        if field == 'uid':
            uid = device[field]
            uri = url_for('get_device', uid=uid, _external=True)
            new_device['uri'] = uri
        else:
            new_device[field] = device[field]
    return new_device


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.route('/xrf-api/v1.0/devices', methods=['GET'])
def get_devices():
    devices = XrfAPI.getInstance().getDevices()
    return jsonify({'devices': [make_public_device(device) for device in devices]})


@app.route('/xrf-api/v1.0/device/<uid>', methods=['GET'])
def get_device(uid):
    devices = XrfAPI.getInstance().getDevices()
    device = [device for device in devices if device['uid'] == uid]
    if len(device) == 0:
        abort(404)
    return jsonify({'device': make_public_device(device[0])})


@app.route('/xrf-api/v1.0/discover/<int:channel>', methods=['GET'])
def discover_devices(channel):
    XrfAPI.getInstance().setChannel(channel)
    devices = XrfAPI.getInstance().IDRequestAll(0xFF)
    return jsonify({'devices':  [make_public_device(device) for device in devices]})


@app.route('/xrf-api/v1.0/setchannel/<int:channel>', methods=['GET'])
def set_channel(channel):
    XrfAPI.getInstance().setChannel(channel)
    return jsonify({'result': 'success'})


def main():
    XrfAPI.getInstance().start()
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)


if __name__ == '__main__':
    main()


