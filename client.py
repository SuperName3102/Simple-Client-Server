import socket
import sys
import traceback
import os

total_codes = '7'   # global
chunk_size = 65536  # global
len_field = 8      # global


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
    will add 16 bytes message length as first field
    e.g. from 'abcd' will send  b'00000004|abcd'
    return: void
    """
    global len_field
    bytearray_data = str(len(bdata)).zfill(len_field).encode() + b'|' + bdata
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
        return 'SCRS|' + input('Enter location to save screenshot at (leave empty for current path): ')
    elif from_user == '2':
        return 'GETF|' + input('Enter location of file to copy: ') + '|' + input("Enter location to copy to: ")
    elif from_user == '3':
        return 'DIRS|' + input('Enter the dir you want (leave empty if you want the current dir): ')
    elif from_user == '4':
        return 'DELF|' + input('Enter the file you want to delete: ')
    elif from_user == '5':
        return 'COPF|' + input('Enter the file you want to copy: ') + '|' + input("Enter location to copy to: ")
    elif from_user == '6':
        return 'RUNP|' + input('Enter the process name/path you want to start: ')
    elif from_user == total_codes:
        return 'EXIT'
    else:
        return ''


def save_file(save_loc, size, sock):
    try:
        global chunk_size
        left = size % chunk_size
        data = b''
        f = open(save_loc, 'wb')
        for i in range(size // chunk_size):
            while len(data) < chunk_size:
                data += sock.recv(chunk_size-len(data))
            f.write(data)
            data = b''
        while len(data) < left:
            data += sock.recv(left - len(data))
        f.write(data)
        print(f"{save_loc} File saved, size: {os.path.getsize(save_loc)}")
        f.close()
    except Exception as e:
        print(e)


def protocol_parse_reply(reply, sock):
    """
    parse the server reply and prepare it to user
    return: answer from server string
    """

    to_show = 'Invalid reply from server'
    try:
        reply = reply.decode()
        fields = reply.split('|')
        fields.pop(0)
        code = fields[0]
        if code == 'ERRR':
            to_show = 'Server return an error: ' + fields[1] + ' ' + fields[2]
        elif code == 'EXTR':
            to_show = 'Server acknowledged the exit message'
        elif code == 'SCRR':
            to_show = f'Screenshot was saved at: {fields[1]}'
        elif code == 'GETR':
            size = int(fields[3])
            path = fields[2]
            file_loc = fields[1]
            save_file(path, size, sock)
            to_show = f'File {file_loc} was saved at: {path}'

        elif code == 'DIRR':
            to_show = f'Contents of dir {fields[1]}: {fields[2]}'
        elif code == 'DELR':
            to_show = f'File {fields[1]} was deleted'
        elif code == 'COPR':
            to_show = f'File {fields[1]} was copied to {fields[2]}'
        elif code == 'RUNR':
            to_show = f'Process {fields[1]} has started'

    except Exception as e:
        print('Server replay bad format ' + str(e))
    return to_show


def handle_reply(reply, sock):
    """
    get the tcp upcoming message and show reply information
    return: void
    """
    to_show = protocol_parse_reply(reply, sock)
    if to_show != '':
        print('\n==========================================================')
        print(f'  SERVER Reply: {to_show}')
        print('==========================================================')


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
        while (len(msg) < msg_len):
            chunk = sock.recv(msg_len - len(msg))
            if not chunk:
                print('Server disconnected abnormally.')
                break
            msg += chunk
        entire_data += msg
        return entire_data
    except Exception as err:
        print('Invalid format')


def main(ip):
    global total_codes
    """
    main client - handle socket and main loop
    """
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
        to_send = protocol_build_request(from_user)
        if to_send == '':
            print("Selection error try again")
            continue
        try:
            send_data(sock, to_send.encode())
            entire_data = recv_data(sock)
            logtcp('recv', entire_data)
            handle_reply(entire_data, sock)

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
