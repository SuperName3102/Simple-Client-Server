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

all_to_die = False  # global
chunk_size = 65536  # global
len_field = 8      # global

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
    will add 16 bytes message length as first field
    e.g. from 'abcd' will send  b'00000004|abcd'
    return: void
    """
    global len_field

    bytearray_data = str(len(bdata)).zfill(len_field).encode() + b'|' + bdata
    sock.send(bytearray_data)
    logtcp('sent', tid, bytearray_data)
    print("")


def check_length(message):
    """
    check message length
    return: string - error message
    """
    global len_field

    size = len(message)
    if size < 21:  # 13 is min message size
        return b'ERRR|003|Bad Format message too short'
    if int(message[:16].decode()) != size - len_field + 1:
        return b'ERRR|003|Bad Format, incorrect message length'
    return b''


def screenshot_save(loc):
    image = pyautogui.screenshot()
    image_name = "screenshot_" + datetime.datetime.now().strftime('%H_%M_%S_%f')+'.jpg'
    loc = os.path.join(loc, image_name)
    image.save(os.path.normpath(loc))
    return loc


def send_file_data(copy_loc, save_loc, sock, tid):
    global chunk_size

    if(not os.path.isfile(copy_loc)):
        start_string = b'ERRR|007|file does not exist'
        send_data(sock, tid, start_string)
        return

    size = os.path.getsize(copy_loc)
    left = size % chunk_size
    start_string = b'GETR|' + copy_loc.encode() + b'|' + save_loc.encode() + b'|' + str(size).encode()
    send_data(sock, tid,  start_string)
    f = open(copy_loc, 'rb')
    for i in range(size//chunk_size):
        data = f.read(chunk_size)
        sock.send(data)
    data = f.read(left)
    sock.send(data)
    f.close()

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

def protocol_build_reply(request):
    """
    Application Business Logic
    function despatcher ! for each code will get to some function that handle specific request
    Handle client request and prepare the reply info
    string:return: reply
    """

    fields = request.decode()
    fields = fields.split('|')
    fields.pop(0)
    code = fields[0]

    if code == 'EXIT':
        reply = 'EXTR'

    elif code == "SCRS":
        if(fields[1]==''):
            reply = f'SCRR|{screenshot_save(str(os.path.abspath(os.getcwd())))}'
        elif (not os.path.isabs(fields[1])):
            reply = 'ERRR|005|path not valid'
        else:
            reply = f'SCRR|{screenshot_save(fields[1])}'


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
        result = run_process(fields[1])
        if (result!=fields[1]):
            reply = f'ERRR|008|process {fields[1]} does not exist'
        else:
            reply = f'RUNR|{result}'


    else:
        reply = 'ERRR|002|code not supported'
        fields = ''
    return reply.encode()


def handle_request(request):
    """
    Hadle client request
    tuple :return: return message to send to client and bool if to close the client socket
    """
    global len_field
    try:
        request_code = request[len_field+1:len_field+4]
        to_send = protocol_build_reply(request)
        if request_code == b'EXIT':
            return to_send, True
    except Exception as err:
        print(traceback.format_exc())
        to_send = b'ERRR|001|General error'
    return to_send, False

def recv_data(sock):
    global len_field

    msg_len = b''
    while (len(msg_len) < len_field):
        msg_len += sock.recv(len_field - len(msg_len))
    dump = sock.recv(1)
    entire_data = msg_len + dump
    if msg_len == b'':
        print('Seems client disconnected')
    msg = b''
    try:
        msg_len = int(msg_len)
    except Exception as err:
        print('Invalid format')
    while (len(msg) < msg_len):
        chunk = sock.recv(msg_len - len(msg))
        if not chunk:
            print('Server disconnected abnormally.')
            break
        msg += chunk
    entire_data += msg
    return entire_data

def handle_client(sock, tid, addr):
    """
    Main client thread loop (in the server),
    :param sock: client socket
    :param tid: thread number
    :param addr: client ip + reply port
    :return: void
    """
    global all_to_die

    finish = False
    print(f'New Client number {tid} from {addr}')
    while not finish:
        if all_to_die:
            print('will close due to main server issue')
            break
        try:
            entire_data = recv_data(sock)
            logtcp('recv', tid, entire_data)
            fields = entire_data.decode()
            fields = fields.split('|')
            fields.pop(0)
            code = fields[0]
            if (code == 'GETF'):
                send_file_data(fields[1], fields[2], sock, tid)
            else:
                to_send, finish = handle_request(entire_data)
                if to_send != '':
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
    sock.close()


def main():
    global all_to_die
    """
	main server loop
	1. accept tcp connection
	2. create thread for each connected new client
	3. wait for all threads
	4. every X clients limit will exit
	"""
    threads = []
    srv_sock = socket.socket()

    srv_sock.bind(('0.0.0.0', 1233))

    srv_sock.listen(20)

    # next line release the port
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    i = 1
    while True:
        print('\nMain thread: before accepting ...')
        cli_sock, addr = srv_sock.accept()
        t = threading.Thread(target=handle_client,
                             args=(cli_sock, str(i), addr))
        t.start()
        i += 1
        threads.append(t)
        if i > 100000000:     # for tests change it to 4
            print('\nMain thread: going down for maintenance')
            break

    all_to_die = True
    print('Main thread: waiting to all clints to die')
    for t in threads:
        t.join()
    srv_sock.close()
    print('Bye ..')


if __name__ == '__main__':
    main()
