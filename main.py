
import time
import requests
import cv2
import numpy as np
import json
import ollama

SYSTEM_PROMPT = """You are an autonomous camera operator for an ESP32-CAM.
Your task is to aim the camera at the target requested by the user.

Camera Setup:
- Channel 0: . Range: 0 (down), to 120 (up). Default: 90.
- Channel 1: . Range: 0 (backward), to 120 (forward). Default: 90.

RESPONSE FORMAT RULES:
You MUST ALWAYS reply in strict JSON format with ONLY these two keys:
1. "message": A short explanation of what you see and what action you are taking.
2. "angles": An object with "channel_0" and "channel_1" integer values (0-180). 
   If no movement is needed, return the current angles.

JSON Example:
{
  "message": "I see the object on the left. Rotating left to center it.",
  "angles": {
    "channel_0": 45,
    "channel_1": 90
  }
}"""

ESP_IP = "your_esp32_ip_here"  # Replace with your ESP32-CAM IP address
URL_SERVO = f"http://{ESP_IP}/servo"
URL_SNAPSHOT = f"http://{ESP_IP}/capture"

#default angles
current_angles = {0: 90, 1: 90}

def set_camera_angle(channel, angle):
    global current_angles
    angle = max(0, min(180, int(angle)))
    try:
        res = requests.get(URL_SERVO, params={"channel": channel, "angle": angle}, timeout=2)
        if res.status_code == 200:
            current_angles[channel] = angle
            return True
    except Exception as e:
        print(f"[Servo Error]: {e}")
    return False

def capture_photo():
    try:
        res = requests.get(URL_SNAPSHOT, timeout=3)
        if res.status_code == 200:
            img_arr = np.asarray(bytearray(res.content), dtype=np.uint8)
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            filename = "current_view.jpg"
            cv2.imwrite(filename, img)
            return filename
    except Exception as e:
        print(f"[Camera Error]: {e}")
    return None

def process_command(user_request):
    print(f"\n=== Command: {user_request} ===")
    
    photo_path = capture_photo()
    if not photo_path:
        print("error: unable to capture photo.")
        return

    # send the current angles to the model
    user_prompt = (
        f"User request: '{user_request}'.\n"
        f"Current camera position: Channel 0 = {current_angles[0]}°, Channel 1 = {current_angles[1]}°.\n"
        f"Analyze the attached image and reply in JSON."
    )
    print(user_prompt)
    try:
        # request format='json'
        response = ollama.chat(
            model='gemma3:4b', #can be changed to any other model, but needs to have vision capabilities
            format='json',     
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt, 'images': [photo_path]}
            ]
        )

        # get text
        raw_text = response['message']['content']
        data = json.loads(raw_text)

        print(f"\n[AI Response]: {data.get('message')}")
        
        # parse angles
        new_angles = data.get('angles', {})
        target_ch0 = new_angles.get('channel_0', current_angles[0])
        target_ch1 = new_angles.get('channel_1', current_angles[1])

        # if angles are different, move the camera
        moved = False
        if target_ch0 != current_angles[0]:
            print(f"[Movement] Channel 0: {current_angles[0]}° -> {target_ch0}°")
            set_camera_angle(0, target_ch0)
            moved = True

        if target_ch1 != current_angles[1]:
            print(f"[Movement] Channel 1: {current_angles[1]}° -> {target_ch1}°")
            set_camera_angle(1, target_ch1)
            moved = True

        if moved:
            print("[Success] Camera moved to new position.")
        else:
            print("[info] No movement required.")

    except json.JSONDecodeError:
        print(f"[error JSON]: unable to parse the answer from AI: {raw_text}")
    except Exception as e:
        print(f"[error]: {e}")

if __name__ == "__main__":
    while True:
        cmd = input("\ncommand (or 'exit'): ").strip()
        if cmd.lower() in ['exit', 'quit']:
            break
        process_command(cmd)
        