import socket
import requests

ESP32_IP = "192.168.1.113" 
URL=f"http://{ESP32_IP}/servo"
def main():
    while True:
        print("\nEnter the channel (0-15) and angle (0-180) to move the servo, or type 'exit' to quit.")
        print("if no channel is specified, channel 0 will be used by default.")
        raw_input=input("Command: ").strip().lower()
        if raw_input in ["exit", "quit"]:
            break
        parts= raw_input.split()
        if len(parts) == 1:
            channel = 0
            angle_str = parts[0]
        elif len(parts) == 2:
            channel_str, angle_str = parts
            if not channel_str.isdigit():
                print("Error: Channel must be a number between 0 and 15.")
                continue
            channel = int(channel_str)
        else:
            print("Error: Invalid input format.")
            continue
        if not angle_str.isdigit():
            print("Error: Angle must be an integer.")
            continue
        angle = int(angle_str)
        if not (0 <= angle <= 180) or not (0 <= channel <= 15):# make sure the range of motion allowes for the angle and channel to move
            print("Error: Angle must be between 0 and 180, Channel must be between 0 and 15.")
            continue
        try:
            params = {"angle": angle, "channel": channel}
            response = requests.get(URL, params=params, timeout=3)
            if response.status_code == 200:
                print(f"Response: {response.text}")
            else:
                print(f"Server error: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Connection error: {e}")

if __name__ == "__main__":
    main()