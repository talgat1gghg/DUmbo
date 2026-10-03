
import time
import requests
import cv2
import numpy as np
import json
import ollama

SYSTEM_PROMPT = """You are an autonomous camera operator on an ESP32-CAM.
Your job is to execute multi-step movement commands or search tasks.

Camera Specs:
- Channel 1:. Range: 20 (forward) to 120 (backward). Default: 90.
- Channel 0: Vertical (Tilt). Range: 20 (Down) to 120 (Up). Default: 90.

RESPONSE FORMAT RULES:
You MUST reply in strict JSON format with these exact keys:
1. "message": Reason for the current action or progress update.
2. "angles": An object with "channel_0" and "channel_1" targets (0-180).
3. "status": String, either "continue" or "complete".
   - Use "continue" if the task requires another step (e.g., target not found yet, or moving to the next position in a multi-step command).
   - Use "complete" if the target is found, the sequence is finished, or no further movement is possible.

JSON Example:
{
  "message": "Scanning to the right, target object not seen yet.",
  "angles": {
    "channel_0": 120,
    "channel_1": 90
  },
  "status": "continue"
}"""

ESP_IP = "192.168.1.113"  # Replace with your ESP32-CAM IP address
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

def run_multi_step_command(user_request, max_steps=5):
    print(f"\n=== Command: {user_request} ===")

    step_history = [] # to keep track of previous steps and angles

    for step in range(1, max_steps + 1):
        print(f"\n--- Step {step}/{max_steps} ---")
    
        photo_path = capture_photo()
        if not photo_path:
            print("error: unable to capture photo.")
            return
        
        #giving the model the last 3 steps of history for context
        history_text = "\n".join(step_history[-3:])# keep last 3 steps in history
    
        # send the current angles to the model
        user_prompt = (
            f"Original Goal: '{user_request}'\n"
            f"Current Angles: Channel 0 = {current_angles[0]}°, Channel 1 = {current_angles[1]}°.\n"
            f"Recent history:\n{history_text}\n"
            f"Analyze the image, update angles if needed, and set status to 'continue' or 'complete'."
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
            status = data.get("status", "complete").lower()
            new_angles = data.get('angles', {})
            target_ch0 = new_angles.get('channel_0', current_angles[0])
            target_ch1 = new_angles.get('channel_1', current_angles[1])

            print(f"[STATUS]: {status}")

            #remebering the step history for context in the next step
            step_history.append(f"Step {step}: moved to (Ch0:{target_ch0}, Ch1:{target_ch1}), status:{status}")

            # if the status is complete we break the loop
            if status == "complete":
                print("\n[Success] AI reached the goal")
                break

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

    else:
        print("\n[info] Maximum steps reached.")

if __name__ == "__main__":
    while True:
        cmd = input("\ncommand (or 'exit'): ").strip()
        if cmd.lower() in ['exit', 'quit']:
            break
        run_multi_step_command(cmd)
        