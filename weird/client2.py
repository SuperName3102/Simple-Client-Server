
import socket
import sys
import traceback
import threading
import cv2
import numpy as np
from io import BytesIO
from PIL import Image

total_codes = '8'

def logtcp(dir, byte_data):
    """
    log direction and all TCP byte array data
    return: void
    """
    if dir == 'sent':
        print(f'C LOG:Sent     >>>{byte_data}')
    else:
        print(f'C LOG:Recieved <<<{byte_data}')


def send_data(sock, bdata):
    """
    send to client byte array data
    will add 8 bytes message length as first field
    e.g. from 'abcd' will send  b'00000004|abcd'
    return: void
    """
    bytearray_data = str(len(bdata)).zfill(8).encode() + b'|' + bdata
    sock.send(bytearray_data)
    logtcp('sent', bytearray_data)


def menu():
    global total_codes
    print('\n  1. save screenshot in location')
    print('\n  2. copy file to client')
    print('\n  3. get dir contents of specific or current dir')
    print('\n  4. delete file from server')
    print('\n  5. copy file in server to a different location')
    print('\n  6. run process in server')
    print(f'\n  {total_codes}. notify exit')
    print()
    return input(f'Input 1 - {total_codes} > ')


def protocol_build_request(from_user):
    global total_codes
    """
    build the request according to user selection and protocol
    return: string - msg code
    """
    if from_user == '1':
        return 'SCRS|' + input('Enter location to save screenshot at: ')
    elif from_user == '2':
        return 'GETF|' + input('Enter location of file to copy: ') + '|' + input("Enter location to copy to: ")
    elif from_user == '3':
        return 'DIRS|' + input('Enter the dir you want (leave empty if you want the current dir: ')
    elif from_user == '4':
        return 'DELF|' + input('Enter the file you want to delete: ')
    elif from_user == '5':
        return 'COPF|' + input('Enter the file you want to copy: ') + '|' + input("Enter location to copy to: ")
    elif from_user == '6':
        return 'RUNP|' + input('Enter the process name/path you want to start: ')
    elif from_user == '7':
        return 'LIVV'
    elif from_user == total_codes:
        return 'EXIT'
    else:
        return ''


def save_file(save_loc, data):
    f = open(save_loc, 'wb')
    f.write(data)
    f.close()

def protocol_parse_reply(reply):
    """
    parse the server reply and prepare it to user
    return: answer from server string
    """

    to_show = 'Invalid reply from server'
    try:
        if(reply[0:4] == b'GETR'):
            fields = reply.split(b'|')
            path = fields[-1].decode()
            file_loc = fields[-2].decode()
            fields.pop(-1)
            fields.pop(-1)
            fields.pop(0)
            data = b'|'.join(fields)
            save_file(path, data)
            to_show = f'File {file_loc} was saved at: {path}'
            return to_show
        reply = reply.decode()
        if '|' in reply:
            fields = reply.split('|')
        code = fields[0]
        if code == 'ERRR':
            to_show = 'Server return an error: ' + fields[1] + ' ' + fields[2]
        elif code == 'EXTR':
            to_show = 'Server acknowledged the exit message'
        elif code == 'SCRR':
            to_show = f'Screenshot was saved at: {fields[1]}'
        elif code == 'DIRR':
            to_show = f'Contents of dir {fields[1]}: {fields[2]}'
        elif code == 'DELR':
            to_show = f'File {fields[1]} was deleted'
        elif code == 'COPR':
            to_show = f'File {fields[1]} was copied to {fields[2]}'
        elif code == 'RUNR':
            to_show = f'Process {fields[1]} has started'

    except Exception as e:
        print('Server replay bad format' + str(e))
    return to_show





def handle_reply(reply):
    """
    get the tcp upcoming message and show reply information
    return: void
    """
    to_show = protocol_parse_reply(reply)
    if to_show != '':
        print('\n==========================================================')
        print(f'  SERVER Reply: {to_show}')
        print('==========================================================')


def request_live_video(sock):
    try:
        while True:
            send_data(sock, 'LIVV'.encode())

            msg_len = b''
            while len(msg_len) < 8:
                msg_len += sock.recv(8 - len(msg_len))

            dump = sock.recv(1)
            entire_data = msg_len + dump

            if msg_len == b'':
                print('Seems server disconnected abnormal')
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
            logtcp('recv', entire_data)

            # Extracting image data from the message
            img_data = msg[9:]  # Assuming the message format is "LIVR|<length>|<image_data>"

            # Convert the image data to a NumPy array
            img_np = np.frombuffer(img_data, dtype=np.uint8)

            try:
                # Display the image directly without using cv2.imdecode
                if img_np is not None and img_np.size > 0 and img_np.shape[0] > 0 and img_np.shape[1] > 0:
                    cv2.imshow("Live Video", img_np.reshape((img_np.shape[0], img_np.shape[1], -1)))
                    cv2.waitKey(1)  # Adjust the delay as needed
            except Exception as cv_err:
                print(f'Error in displaying live video: {cv_err}')

    except Exception as err:
        print(f'Error in sending/receiving live video: {err}')


def main(ip):
    global total_codes

    # ... (unchanged)

    connected = False

    sock = socket.socket()

    port = 1233
    try:
        sock.connect((ip, port))
        print(f'Connect succeeded {ip}:{port}')
        connected = True
    except:
        print(
            f'Error while trying to connect.  Check ip or port -- {ip}:{port}')

    while connected:
        from_user = menu()

        if from_user == '7':
            # Start a separate thread for live video
            video_thread = threading.Thread(target=request_live_video, args=(sock,))
            video_thread.start()
        else:
            to_send = protocol_build_request(from_user)

            if to_send == '':
                print("Selection error, try again")
                continue

            try:
                send_data(sock, to_send.encode())

                msg_len = b''
                while len(msg_len) < 8:
                    msg_len += sock.recv(8 - len(msg_len))

                dump = sock.recv(1)
                entire_data = msg_len + dump

                if msg_len == b'':
                    print('Seems server disconnected abnormal')
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
                logtcp('recv', entire_data)
                handle_reply(msg)

                if from_user == total_codes:
                    print('Will exit ...')
                    connected = False
                    break
            except socket.error as err:
                print(f'Got socket error: {err}')
                break
            except Exception as err:
                print(f'General error: {err}')
                print(traceback.format_exc())
                break

    print('Bye')
    sock.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main('127.0.0.1')
