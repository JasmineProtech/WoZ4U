from flask import Flask, render_template, Response, url_for, request, send_file, abort, send_from_directory

import yaml
import time
import threading

from utils import is_url
from utils import alImage_to_PIL
from utils import PIL_to_JPEG_BYTEARRAY

import qi
from naoqi import ALProxy
import vision_definitions

from urlparse import unquote

app = Flask(__name__)

@app.route('/')
def index():
    try:
        global qi_session
        if qi_session is not None:
            print("Reconnect")
            global ip
            print(ip)
            return render_template("index.html", config=config, reconnect=True, reconnect_ip=ip)
    except NameError:
        return render_template('index.html', config=config, reconnect=False)

@app.route("/connect_robot")
def connect_robot():
    global ip
    ip = request.args.get('ip', type=str)
    port = 9559


    global qi_session
    qi_session = qi.Session()
    
    try:
        qi_session.connect(str("tcp://" + str(ip) + ":" + str(port)))
    except RuntimeError as msg:
        print("qi session connect error!:")
        print(msg)
    
    tts_srv = qi_session.service("ALTextToSpeech")
    tts_srv.setVolume(0.1)
    tts_srv.say("Connected")
    volume_lvl = tts_srv.getVolume()
    voice_pitch = tts_srv.getParameter("pitchShift")
    voice_pitch = round(voice_pitch, 3)

    al_srv = qi_session.service("ALAutonomousLife")
    autonomous_state = al_srv.getState()

    ba_srv = qi_session.service("ALBasicAwareness")
    engagement_state = ba_srv.getEngagementMode()
    ba_runnning = ba_srv.isRunning()

    ab_srv = qi_session.service("ALAutonomousBlinking")
    blinking_enabled = ab_srv.isEnabled()

    motion_srv = qi_session.service("ALMotion")
    orthogonal_collision = motion_srv.getOrthogonalSecurityDistance()
    orthogonal_collision = round(orthogonal_collision, 3)

    tangential_collision = motion_srv.getTangentialSecurityDistance()
    tangential_collision = round(tangential_collision, 3)

    body_breathing = motion_srv.getBreathEnabled("Body")
    legs_breathing = motion_srv.getBreathEnabled("Legs")
    arms_breathing = motion_srv.getBreathEnabled("Arms")
    head_breathing = motion_srv.getBreathEnabled("Head")

    vel_vec = motion_srv.getRobotVelocity()
    vel_vec = [round(vel, 3) for vel in vel_vec]

    return {
        "status": "ok",
        "ip": ip,
        "autonomous_state": autonomous_state,
        "engagement_state": engagement_state,
        "ba_is_running": ba_runnning,
        "blinking_enabled": blinking_enabled,
        "orthogonal_collision": orthogonal_collision,
        "tangential_collision": tangential_collision,
        "head_breathing": head_breathing,
        "arms_breathing": arms_breathing,
        "body_breathing": body_breathing,
        "legs_breathing": legs_breathing,
        "volume_lvl": volume_lvl,
        "voice_pitch": voice_pitch,
        "velocity_vector": vel_vec
    }

@app.route("/set_autonomous_state")
def set_autonomous_state():
    state = request.args.get('state', type=str)
    print(state)

    al_srv = qi_session.service("ALAutonomousLife")
    al_srv.setState(state)
    time.sleep(2)

    return {
       "status": "ok",
       "state": state 
    }

@app.route("/toggle_setting")
def toggle_setting():
    setting = request.args.get('setting', type=str)
    curr_state = request.args.get('curr_state', type=str)

    print(setting)
    print(curr_state)

    motion_srv = qi_session.service("ALMotion")
    ab_srv = qi_session.service("ALAutonomousBlinking")
    ba_srv = qi_session.service("ALBasicAwareness")


    new_state = None
    if setting == "blinking":
        if curr_state == "ON":
            ab_srv.setEnabled(False)
        else:
            ab_srv.setEnabled(True)
        
        new_state = ab_srv.isEnabled()

    elif setting == "head_breathing":
        if curr_state == "ON":
            motion_srv.setBreathEnabled("Head", False)
        else:
            motion_srv.setBreathEnabled("Head", True)
        
        new_state = motion_srv.getBreathEnabled("Head")

    elif setting == "arms_breathing":
        if curr_state == "ON":
            motion_srv.setBreathEnabled("Arms", False)
        else:
            motion_srv.setBreathEnabled("Arms", True)
        
        new_state = motion_srv.getBreathEnabled("Arms")

    elif setting == "body_breathing":
        if curr_state == "ON":
            motion_srv.setBreathEnabled("Body", False)
        else:
            motion_srv.setBreathEnabled("Body", True)
        
        new_state = motion_srv.getBreathEnabled("Body")

    elif setting == "legs_breathing":
        if curr_state == "ON":
            motion_srv.setBreathEnabled("Legs", False)
        else:
            motion_srv.setBreathEnabled("Legs", True)

        new_state = motion_srv.getBreathEnabled("Legs")

    elif setting == "basic_awareness":
        if curr_state == "ON":
            ba_srv.setEnabled(False)
        else:
            ba_srv.setEnabled(True)
    
        new_state = ba_srv.isEnabled()

    # TODO: toggle setting
    time.sleep(2)

    return {
        "status": "ok",
        "setting": setting,
        "new_state": new_state
    }

@app.route("/say_text")
def say_text():
    msg = request.args.get('msg', type=str)
    print(msg)

    tts = qi_session.service("ALTextToSpeech")
    tts.say(msg)

    return {
       "status": "ok",
       "text": msg,
    }

@app.route("/serve_audio/<path:filename>")
def serve_audio(filename):
    print(filename)
    return send_from_directory(config["audio_root_location"], filename)


@app.route("/play_audio")
def play_audio():
    # doesn't work :/
    # ap_srv = qi_session.service("ALAudioPlayer")
    # ap_srv.playWebStream("https://www2.cs.uic.edu/~i101/SoundFiles/CantinaBand60.wav", 0.1, 0.0)

    index = request.args.get('index', type=int)
    print(index)

    tablet_srv = qi_session.service("ALTabletService")
    tablet_srv.showWebview("http://130.239.183.189:5000/show_img_page/sound_playing.png")

    time.sleep(1)  # to ensure that tablet is ready, otherwise audio might not play...

    location = config["audio_files"][index]["location"]

    if not is_url(location):
        location = "http://130.239.183.189:5000/serve_audio/" + location
        print(location)


    tts_srv = qi_session.service("ALTextToSpeech")
    volume = tts_srv.getVolume()

    js_code = """
        var audio = new Audio('{}'); 
        audio.volume = {};
        audio.play();""".format(location, volume)


    tablet_srv.executeJS(js_code)
    time.sleep(60)  # TODO: dynamic length 
    tablet_srv.hideWebview()

    return {
       "status": "ok",
    }

@app.route("/show_img/<img_name>")
def show_img(img_name):
    tablet_srv = qi_session.service("ALTabletService")
    # very hacky, but this is the only way I got this to work... 
    # Think we have to do it this way, because we don't want the image to be rendered in the main browser, but dispatch it to pepper's tablet
    # TODO: get IP dynamicaly
    tablet_srv.showWebview("http://130.239.183.189:5000/show_img_page/" + img_name)

    # this works as well...:
    # js_code = """
    #    var audio = new Audio('https://www2.cs.uic.edu/~i101/SoundFiles/CantinaBand60.wav'); 
    #    audio.volume = 0.1;
    #    audio.play();"""

    # tablet_srv.executeJS(js_code)

    return {
       "status": "ok",
       "img_name": img_name
    }

@app.route("/show_img_page/<img_name>")
def show_img_page(img_name):
    img_path = "/static/imgs/" + img_name
    img_path = config["image_root_location"] + img_name
    print(img_path)
    return render_template("img_view.html", img_src=img_path)  # WORKS! 

@app.route("/clear_tablet")
def clear_tablet():
        tablet_srv = qi_session.service("ALTabletService")
        tablet_srv.hideWebview()

        return {
            "status": "cleaned tablet webview"
        }

@app.route("/set_engagement_state")
def set_engagement_state():
    state = request.args.get('state', type=str)
    print(state)

    ba_srv = qi_session.service("ALBasicAwareness")
    ba_srv.setEngagementMode(state)

    return {
       "status": "ok",
       "engagement_state": state 
    }

@app.route("/adjust_volume")
def adjust_volume():
    target = request.args.get('volume', type=float)
    target = target / 100.0  # slider range is 1 - 100, api wants 0 - 1 

    tts_srv = qi_session.service("ALTextToSpeech")
    tts_srv.setVolume(target)

    return {
        "status": "ok",
        "volume": target
    } 

@app.route("/exec_anim_speech")
def exec_anim_speech():
    index = request.args.get('index', type=int)
    print(index)

    annotated_text = config["animated_speech"][index]["string"]


    as_srv = qi_session.service("ALAnimatedSpeech")
    as_srv.say(annotated_text)

    return {
        "status": "ok",
        "annotated_text": annotated_text
    }

@app.route("/exec_gesture")
def exec_gesture():
    index = request.args.get('index', type=int)
    print(index)

    gesture = config["gestures"][index]["string"]

    ap_srv = qi_session.service("ALAnimationPlayer")
    ap_srv.run(gesture)

    return {
        "status": "ok",
        "gesture": gesture
    }

@app.route("/exec_custom_gesture")
def exec_custom_gesture():
    string = request.args.get("string", type=str)
    print(string)

    gesture = unquote(string)
    print(gesture)

    ap_srv = qi_session.service("ALAnimationPlayer")
    ap_srv.run(gesture)

    return {
        "status": "ok",
        "gesture": gesture
    }

@app.route("/set_tts_param")
def set_tts_param():
    param = request.args.get("param", type=str)
    value = request.args.get("value", type=float)

    print(value)

    tts_srv = qi_session.service("ALTextToSpeech")

    if param == "pitchShift":
        value = value // 100.0  # for pitch shift we need to adjust the range... nice consistency in the naoqi api >.<
        print(value)
        tts_srv.setParameter(param, value)
    else:
        tts_srv.setParameter(param, value)

    return {
            "status": "ok",
            "param": param,
            "value": value
        }

@app.route("/set_collision_radius")
def set_collision_radius():
    param = request.args.get("param", type=str)
    value = request.args.get("value", type=float)
    print(param)
    print(value)

    time.sleep(1)

    motion_srv = qi_session.service("ALMotion")

    # get function dynamically from service object
    call = motion_srv.__getattribute__("set" + param + "SecurityDistance")
    call(value)

    return {
        "param": param,
        "value": value
    }
@app.route("/update_pepper_velocities")
def update_pepper_velocities():
        axis = request.args.get("axis", type=str)
        val = request.args.get("val", type=float)

        print(axis)
        print(val)

        motion_srv = qi_session.service("ALMotion")
        life_srv = qi_session.service("ALAutonomousLife")

        # Disable all autonomous life features, they can interfere with our commands...
        life_srv.setState("solitary")
        life_srv.setAutonomousAbilityEnabled("All", False)

        # get current robot velocity
        x_vel, y_vel, theta_vel = motion_srv.getRobotVelocity()
        x_vel = round(x_vel, 3)
        y_vel = round(y_vel, 3)
        theta_vel = round(theta_vel, 3)

        # update velocity
        if axis == "x":
            x_vel += val
        elif axis == "theta":
            theta_vel += val

        stiffness = 0.1
        motion_srv.setStiffnesses("Body", stiffness)

        # set velocity
        motion_srv.move(x_vel, y_vel, theta_vel)

        return {
            "x_vel": x_vel,
            "y_vel": y_vel,
            "theta_vel": theta_vel,
            "target_axis": axis,
            "value": val
        }

@app.route("/stop_motion")
def stop_motion():
    motion_srv = qi_session.service("ALMotion")
    motion_srv.stopMove()

    x_vel, y_vel, theta_vel = motion_srv.getRobotVelocity()
    x_vel = round(x_vel, 3)
    y_vel = round(y_vel, 3)
    theta_vel = round(theta_vel, 3)

    return {
        "status": "stopped move",
        "x_vel": x_vel,
        "y_vel": y_vel,
        "theta_vel": theta_vel
    }

@app.route("/resting_position")
def resting_position():
    motion_srv = qi_session.service("ALMotion")
    motion_srv.stopMove()
    motion_srv.rest()

    return {
        "status": "entering resting position move"
    }

@app.route("/netural_stand_position")
def netural_stand_position():
    posture_srv = qi_session.service("ALRobotPosture")
    posture_srv.goToPosture("Stand", 0.5)

    return {
        "status": "entering 'Stand' posture"
    }


@app.route("/move_joint")
def move_joint():
    axis = request.args.get("axis", type=str)
    val = request.args.get("val", type=float)

    stiffness=0.5
    time=1

    motion_srv = qi_session.service("ALMotion")

    if not motion_srv.robotIsWakeUp():
            motion_srv.wakeUp()
    
    motion_srv.setStiffnesses("Head", stiffness)

    motion_srv.angleInterpolation(
        [str(axis)],  # which axis
        [float(val)],  # amount of  movement
        [int(time)],  # time for movement
        False  # in absolute angles
        )

    if "Head" in axis:
        status = "moving head"
    elif "Hip" in axis:
        status = "moving hip"

    return {
        "status": status,
        "axis": axis,
        "val": val,
        "time": time,
        "stiffness": stiffness
    }

@app.route("/camera_view")    
def camera_view():
    video_srv = qi_session.service("ALVideoDevice")

    # see if there are any old subscribers...
    if video_srv.getSubscribers():
        for subscriber in video_srv.getSubscribers():
            video_srv.unsubscribe(subscriber)


    resolution = vision_definitions.kQVGA  # 320 * 240
    colorSpace = vision_definitions.kRGBColorSpace
    global imgClient
    imgClient = video_srv.subscribe("_client", resolution, colorSpace, 5)

    return render_template("camera.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        stream_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame')

def stream_generator():
    video_srv = qi_session.service("ALVideoDevice")
    counter = 0
    try: 
        while True:
            # frame = camera.get_frame()
            global imgClient
            alImage = video_srv.getImageRemote(imgClient)
            if alImage is not None:
                pil_img = alImage_to_PIL(alImage)

                jpeg_bytes = PIL_to_JPEG_BYTEARRAY(pil_img)

                counter += 1

                yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n\r\n')

            time.sleep(0.01)
    except IOError:  # ideally this would catch the error when tab is closed, but it doesnt :/ TODO
        print("removing listener...")
        video_srv = qi_session.service("ALVideoDevice")
        # see if there are any old subscribers...
        if video_srv.getSubscribers():
            for subscriber in video_srv.getSubscribers():
                video_srv.unsubscribe(subscriber)


if __name__ == '__main__':

    global config
    with open("config.yaml", "r") as f:
        # The FullLoader parameter handles the conversion from YAML
        # scalar values to Python the dictionary format
        config = yaml.safe_load(f)
        print(config)

    app.run(host='0.0.0.0', debug=True)