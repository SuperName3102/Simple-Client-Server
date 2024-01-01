import socket
import random
import traceback
import time
import threading
import os
import datetime
import pyautogui
import glob
import shutil
import subprocess
import cv2
from io import BytesIO
from PIL import Image

all_to_die = False  # global

def logtcp(dir, tid, byte_data):
    """
    log direction, tid and all TCP byte array data
    return: void
    """
    if dir == 'sent':
        print(f'{tid} S LOG:Sent     >>> {byte_data}')
    else:
        print(f'{tid} S LOG:Recieved <<< {byte_data}')

def send_data(sock, tid, bdata):
    """
    send to client byte array data
    will add 8 bytes message length as first field
    e.g. from 'abcd' will send  b'00000004|abcd'
    return: void
    """
    bytearray_data = str(len(bdata)).zfill(8).encode() + b'|' + bdata
    sock.send(bytearray_data)
    logtcp('sent', tid, bytearray_data)
    print("")

def check_length(message):
    """
    check message length
    return: string - error message
    """
    size = len(message)
    if size < 13:  # 13 is min message size
        return b'ERRR|003|Bad Format message too short'
    if int(message[:8].decode()) != size - 9:
        return b'ERRR|003|Bad Format, incorrect message length'
    return b''

def screenshot_save(loc):
    image = pyautogui.screenshot()
    image_name = "screenshot_" + datetime.datetime.now().strftime('%H_%M_%S_%f') + '.jpg'
    loc = os.path.join(loc, image_name)
    image.save(os.path.normpath(loc))
    return loc

def send_file_data(copy_loc):
    f = open(copy_loc, 'rb')
    data = f.read()
    f.close()
    return data

def get_dir(path):
    path += '\*.*'
    dir_list = glob.glob(path)
    dir_list = '\n'.join(dir_list)
    return '\n' + dir_list

def del_file(path):
    os.remove(path)
    return

def copy_file(to_cop, cop_loc):
    shutil.copy(to_cop, cop_loc)

def run_process(process):
    try:
        subprocess.Popen(process)
        return process
    except Exception as err:
        return err

def capture_screenshot():
    img = pyautogui.screenshot()
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()

def send_live_video(sock, tid):
    try:
        while True:
            screenshot_data = capture_screenshot()
            send_data(sock, tid, f'LIVR|{len(screenshot_data)}|'.encode() + screenshot_data)
            time.sleep(0.1)  # Adjust the delay as needed
    except Exception as err:
        print(f'Error in sending live video: {err}')

def protocol_build_reply(request):
    """
    Application Business Logic
    function despatcher ! for each code will get to some function that handle specific request
    Handle client request and prepare the reply info
    string:return: reply
    """

    fields = request.decode()
    fields = fields.split('|')
    code = fields[0]
    if code == 'EXIT':
        reply = 'EXTR'

    elif code == "SCRS":
        if (not os.path.isabs(fields[1])):
            reply = 'ERRR|005|path not valid'
        else:
            reply = f'SCRR|{screenshot_save(fields[1])}'

    elif code == 'GETF':
        if (not os.path.isfile(fields[1])):
            reply = 'ERRR|007|file does not exist'
        else:
            reply = b'GETR|' + send_file_data(fields[1]) + b'|' + fields[1].encode() + b'|' + fields[2].encode()
            return reply

    elif(code=='DIRS'):
        if(fields[1]==''):
            reply = f'DIRR|{os.getcwd()}|{get_dir(str(os.path.abspath(os.getcwd())))}'
        else:
            if (not os.path.isdir(fields[1])):
                reply = 'ERRR|006|path does not exist'
            else:
                reply = f'DIRR|{fields[1]}|{get_dir(fields[1])}'

    elif(code=='DELF'):
        if (not os.path.isfile(fields[1])):
            reply = 'ERRR|007|file does not exist'
        else:
            del_file(fields[1])
            reply = f'DELR|{fields[1]}'

    elif(code=='COPF'):
        if (not os.path.isfile(fields[1])):
            reply = 'ERRR|007|file does not exist'
        else:
            copy_file(fields[1], fields[2])
            reply = f'COPR|{fields[1]}|{fields[2]}'
    elif(code=='RUNP'):
        if (run_process(fields[1])!=fields[1]):
            reply = f'ERRR|008|process {fields[1]} does not exist'
        else:
            reply = f'RUNR|{run_process(fields[1])}'

    elif code == 'LIVV':
        reply = 'LIVR'
    else:
        reply = 'ERRR|002|code not supported'
        fields = ''
    return reply.encode()


def handle_request(request):
    try:
        request_code = request[:4]
        to_send = protocol_build_reply(request)
        if request_code == b'EXIT':
            return to_send, True
        elif request_code == b'SCRS':
            # Ignore screenshot requests, they are handled separately
            return b'', False
    except Exception as err:
        print(traceback.format_exc())
        to_send = b'ERRR|001|General error'
    return to_send, False

def handle_client(sock, tid, addr):
    global all_to_die

    finish = False
    print(f'New Client number {tid} from {addr}')
    video_thread = threading.Thread(target=send_live_video, args=(sock, tid))
    video_thread.start()

    while not finish:
        if all_to_die:
            print('Will close due to main server issue')
            break
        try:
            msg_len = b''
            while len(msg_len) < 8:
                msg_len += sock.recv(8 - len(msg_len))
            dump = sock.recv(1)
            entire_data = msg_len + dump

            if msg_len == b'':
                print('Seems client disconnected')
                break

            msg_len = int(msg_len)
            msg = b''
            while len(msg) < msg_len:
                chunk = sock.recv(msg_len - len(msg))
                if not chunk:
                    print('Server disconnected abnormally.')
                    break
                msg += chunk
            entire_data += msg
            logtcp('recv', tid, entire_data)
            to_send, finish = handle_request(msg)
            if to_send != b'':
                send_data(sock, tid, to_send)
            if finish:
                time.sleep(1)
                break
        except socket.error as err:
            print(f'Socket Error exit client loop: err:  {err}')
            break
        except Exception as err:
            print(f'General Error %s exit client loop: {err}')
            print(traceback.format_exc())
            break

    print(f'Client {tid} Exit')
    video_thread.join()  # Wait for the video thread to finish
    sock.close()

def main():
    global all_to_die

    threads = []
    srv_sock = socket.socket()

    srv_sock.bind(('0.0.0.0', 1233))

    srv_sock.listen(20)
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    i = 1
    while True:
        print('\nMain thread: before accepting ...')
        cli_sock, addr = srv_sock.accept()
        t = threading.Thread(target=handle_client, args=(cli_sock, str(i), addr))
        t.start()
        i += 1
        threads.append(t)
        if i > 100000000:  # for tests change it to 4
            print('\nMain thread: going down for maintenance')
            break

    all_to_die = True
    print('Main thread: waiting for all clients to die')
    for t in threads:
        t.join()
    srv_sock.close()
    print('Bye ..')

if __name__ == '__main__':
    main()