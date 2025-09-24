import cv2
import mediapipe as mp
import time
import asyncio
import websockets
import json
import threading
from queue import Queue

# --- Configuration ---
WEBSOCKET_URI = "ws://localhost:3000/ws"
FIST_COOLDOWN = 2.0  # Cooldown in seconds
HOVER_TIME = 0.8     # Time to hover to select
BUTTON_SIZE = (120, 80)
BUTTON_NAMES = ["A", "B", "C", "D"]

# --- Shared State (Thread-Safe) ---
message_queue = Queue()
game_state = "WAITING_FOR_FIST"
state_lock = threading.Lock()

# --- MediaPipe Setup ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.5)
mp_draw = mp.solutions.drawing_utils

# ========================================================================================
# THREAD 1: CAMERA AND GESTURE RECOGNITION
# ========================================================================================
def camera_and_gesture_thread():
    global game_state
    last_fist_time = 0
    hover_start_time = None
    last_hovered_button = None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("CAMERA_THREAD: Error: Could not open webcam.")
        message_queue.put("EXIT")
        return

    while True:
        success, img = cap.read()
        if not success:
            time.sleep(0.01)
            continue

        img = cv2.flip(img, 1)
        img_height, img_width, _ = img.shape
        
        with state_lock:
            current_state = game_state

        results = hands.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            if current_state == "WAITING_FOR_FIST":
                if is_fist(hand_landmarks) and (time.time() - last_fist_time > FIST_COOLDOWN):
                    print("CAMERA_THREAD: Fist detected! Putting message in queue...")
                    message_queue.put(json.dumps({"action": "requestDiceRoll"}))
                    last_fist_time = time.time()
                    with state_lock:
                        game_state = "WAITING_FOR_SERVER_RESPONSE"

            elif current_state == "WAITING_FOR_ANSWER":
                buttons = draw_buttons(img, img_width)
                finger_tip_pos = get_finger_tip_pos(hand_landmarks, img_width, img_height)

                if finger_tip_pos:
                    cv2.circle(img, finger_tip_pos, 10, (0, 255, 0), cv2.FILLED)
                    current_hovered_button = check_hover(finger_tip_pos, buttons)
                    
                    if current_hovered_button:
                        highlight_button(img, buttons, current_hovered_button)
                    
                    if current_hovered_button and current_hovered_button == last_hovered_button:
                        if time.time() - hover_start_time > HOVER_TIME:
                            print(f"CAMERA_THREAD: Answer selected: {current_hovered_button}")
                            message_queue.put(json.dumps({"action": "submitAnswer", "answer": current_hovered_button}))
                            hover_start_time = None
                            with state_lock:
                                game_state = "WAITING_FOR_SERVER_RESPONSE"
                    else:
                        last_hovered_button = current_hovered_button
                        hover_start_time = time.time() if current_hovered_button else None
        
        cv2.putText(img, f"State: {current_state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        cv2.imshow("Gesture Controller", img)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            message_queue.put("EXIT")
            break
        
        time.sleep(0.01) # Yield control to other threads

    cap.release()
    cv2.destroyAllWindows()

# ========================================================================================
# THREAD 2: WEBSOCKET COMMUNICATION
# ========================================================================================
async def websocket_communication_thread():
    try:
        async with websockets.connect(WEBSOCKET_URI) as websocket:
            print("WEBSOCKET_THREAD: Connected to WebSocket server.")
            
            listen_task = asyncio.create_task(listen_for_server_messages(websocket))
            send_task = asyncio.create_task(send_messages_from_queue(websocket))
            
            done, pending = await asyncio.wait([listen_task, send_task], return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

    except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError):
        print("WEBSOCKET_THREAD: Connection failed or was lost. Ensure the server is running.")
    except Exception as e:
        print(f"WEBSOCKET_THREAD: An error occurred: {e}")

async def listen_for_server_messages(websocket):
    global game_state
    print("LISTENER_TASK: Started and waiting for messages from server...")
    async for message in websocket:
        # --- DEBUGGING STEP ---
        # This log is crucial. It confirms the controller has received the server's response.
        print(f"LISTENER_TASK: Received raw message from server: {message}")
        data = json.loads(message)
        server_command = data.get('sub_action') 
        with state_lock:
            if server_command == 'waitForAnswer' and game_state != "WAITING_FOR_ANSWER":
                print("LISTENER_TASK: State changing to WAITING_FOR_ANSWER")
                game_state = "WAITING_FOR_ANSWER"
            elif server_command == 'waitForFist' and game_state != "WAITING_FOR_FIST":
                print("LISTENER_TASK: State changing to WAITING_FOR_FIST")
                game_state = "WAITING_FOR_FIST"

async def send_messages_from_queue(websocket):
    print("SENDER_TASK: Started and waiting for messages from queue...")
    while True:
        if not message_queue.empty():
            message = message_queue.get()
            if message == "EXIT":
                print("SENDER_TASK: EXIT signal received. Shutting down.")
                break
            print(f"SENDER_TASK: Sending message to server: {message}")
            await websocket.send(message)
        await asyncio.sleep(0.1)

# --- Helper Functions ---
def is_fist(hand_landmarks):
    try:
        finger_tips = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
        finger_pips = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
        for tip_id, pip_id in zip(finger_tips, finger_pips):
            if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y: return False
        return True
    except: return False

def draw_buttons(img, img_width):
    button_y = 50
    total_width = (BUTTON_SIZE[0] + 20) * len(BUTTON_NAMES) - 20
    start_x = (img_width - total_width) // 2
    buttons_rects = []
    for i, name in enumerate(BUTTON_NAMES):
        x = start_x + i * (BUTTON_SIZE[0] + 20)
        cv2.rectangle(img, (x, button_y), (x + BUTTON_SIZE[0], button_y + BUTTON_SIZE[1]), (255, 0, 0), 3)
        cv2.putText(img, name, (x + 35, button_y + 60), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 4)
        buttons_rects.append((x, button_y, BUTTON_SIZE[0], BUTTON_SIZE[1]))
    return buttons_rects

def highlight_button(img, buttons, hovered_button_name):
    for i, (x, y, w, h) in enumerate(buttons):
        if BUTTON_NAMES[i] == hovered_button_name:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), -1)
            cv2.putText(img, BUTTON_NAMES[i], (x + 35, y + 60), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 0), 4)
            break

def get_finger_tip_pos(hand_landmarks, img_width, img_height):
    tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
    return int(tip.x * img_width), int(tip.y * img_height)

def check_hover(finger_pos, buttons):
    for i, (x, y, w, h) in enumerate(buttons):
        if x < finger_pos[0] < x + w and y < finger_pos[1] < y + h: return BUTTON_NAMES[i]
    return None

if __name__ == "__main__":
    cam_thread = threading.Thread(target=camera_and_gesture_thread, daemon=True)
    cam_thread.start()
    asyncio.run(websocket_communication_thread())

