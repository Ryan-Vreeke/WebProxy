# Place your imports here
from glob import glob
from socket import *
import signal
import sys
from optparse import OptionParser
from _thread import *
from threading import Thread
import threading
import time

from urllib.parse import urlparse
import re


class Proxy:#a class that holds the current setting of the proxy

    def __init__(self, caching, blocking):
        self.caching = caching#turns on caching
        self.blocking = blocking


def ctrl_c_pressed(signal, frame):
    sys.exit(0)


# TODO: Put function definitions here

#**********************
# takes in a string and returns true if it is the ending characters \r\n\r\n 
# *
def is_incomplete_request(line: str) -> bool:
    if(line.endswith("\\r\\n\\r\\n") or "\\r\\n\\r\\n" in line or line.endswith("\r\n\r\n") or "\r\n\r\n" in line):
        return False
    return True

###########
# chacks if the url is and absolute url or a uri 
# http://www.google.com -> true
# www.google.com -> false
# #
def is_absolute(url):
    return bool(urlparse(url).netloc)#uses urlparse. if netloc isn't empty then its a absolute

#checks if this is a valid url
def is_validURL(url):
    if(is_absolute(url)):#if it is and absolute url then check if it has a path.
        return bool(urlparse(url).path)
    else:
        return False


def save_to_file(filename, resonse):
    print('saving')
    with open(filename, 'wb') as file:#saves response as a byte string using the filename
        file.write(resonse)

#returns a byte str
def read_from_file(filename):
    with open(filename, 'rb') as file:#reads the cached file using the file name. 
        content = file.read()
    return content

##helper method that sends the error code to the connectedSocket
def send_error(error, connectionSocket):
    try:
        if(error == 400):
            connectionSocket.send("HTTP/1.0 400 Bad Request\r\n".encode())
        elif(error == 501):
            connectionSocket.send("HTTP/1.0 501 Not Implemented\r\n".encode())
        elif(error == 403):
            connectionSocket.send("HTTP/1.0 403 Forbidden\r\n".encode())
    except Exception as e:
        print(e)


cache = {}#dictionary that hold the cached filename and uses url+path as the key
blocklist = []
lock = threading.Lock()
info = Proxy(False, False)


def request_validate(request: str, connectionSocket):
    strings = request.split("\r\n")
    sendPort = 80#setting the default port to send the request to 80

    # check if request was empty
    if(strings[0] == ''):
        send_error(400, connectionSocket)
    else:
        requestLine = strings[0]#gets the request line from the full request
        url = ''
        headers = ''
        path = ''

        #check if GET is in the request
        if('GET' not in requestLine):
            if('POST' in requestLine or 'CONNECT' in requestLine or 'HEAD' in requestLine):
                send_error(501, connectionSocket)
                connectionSocket.close()
                return ("False", sendPort, url, path)
            else:
                send_error(400, connectionSocket)#send error 400 and return out of the the request validation with a false flag set
                connectionSocket.close()#close connection
                return ("False", sendPort, url, path)


        # check url
        if(len(requestLine.split(' ')) > 1):

            try:
                parsedURL = urlparse(requestLine.split(' ')[1])#get just the url with out the path and place it in the urlparseer
                #url validation
                if(is_validURL(requestLine.split(' ')[1])):
                    url = parsedURL.hostname#get the url 
                    path = parsedURL.path #get the path
                    if(bool(parsedURL.port)):#if there is a port then use that 
                        sendPort = parsedURL.port

                else:
                    send_error(400, connectionSocket)#sends 400 error because the url wasn't formed correctly
                    connectionSocket.close()
                    return ("False", sendPort, url, path)

            except:
                send_error(400, connectionSocket)#error for url not correctly formatted
                connectionSocket.close()
                return ("False", sendPort, url, path)

            if(requestLine.split(' ')[1] == ''):#if request line is empty then error
                send_error(400, connectionSocket)
                connectionSocket.close()
                return ("False", sendPort, url, path)
            else:
                url = urlparse(requestLine.split(' ')[1]).hostname

            # check if request line contains HTTP/1.0 protocol
            if("HTTP/1.0" not in requestLine):
                send_error(400, connectionSocket)
                connectionSocket.close()
                return ("False", sendPort, url, path)
            
            if('' != strings[1]):
                # check header are formatted correctly
                for x in range(1, len(strings) - 1):#loop through all of the header locations
                    if(": " in strings[x]):#if there is a : then check if it is a valid header
                        head = strings[x].split(':')[0]
                        if(not head.endswith(" ")):#make sure there isn't a space before the :
                            if("Connection" not in head):
                                headers += "\r\n" + strings[x]#add the header to a list of headers. so it can be appended to the send request
                        else:
                            send_error(400, connectionSocket)
                            connectionSocket.close()
                            return ("False", sendPort, url, path)
                    elif(strings[x] != ''):
                        send_error(400, connectionSocket)
                        connectionSocket.close()
                        return ("False", sendPort, url, path)

            # return an unfinished request so correct headers can be appended
            sendRequest = f"GET {path} HTTP/1.0\r\nHost: {url}{headers}\r\n"
            return (sendRequest, sendPort, url, path)
  
        else:
            send_error(400, connectionSocket)
            connectionSocket.close()

#send to server method
def send_to_server(request: str, url, port):
    s = socket(AF_INET, SOCK_STREAM)
    s.connect((url, port))#connect using tcp 
    s.settimeout(5)
    response = b''
    s.send(request.encode())#send the request

    #keep recv until the response if finished
    try:
        while True:
            chunk = s.recv(4096)

            if len(chunk) == 0:#keep looping until chunk is 0
                break
            response = response + chunk#append the chunk on to the response
    except TimeoutError as e:#timeout if it is hanging
        print("timeout")

    s.close()#close the server and return
    return response

#checks if the key is in the cache
def inCache(key) -> bool:
    with lock:
        if key in cache:
            return True
        else:
            return False


def out_of_date(response) -> bool:
    return bool(b'304 Not Modified' not in response)


def client_request(connection):
    request = ''
    # loop until empty line is recieved
    while is_incomplete_request(request):  # does exit
        more = connectionSocket.recv(4096).decode()
        request = request + more
    
    try:
        # checks if this is a valid request. then sends back a tiple with the request to send, the port, and the url.
        (sendRequest, sendPort, url, path) = request_validate(
            request, connectionSocket)
    except Exception as e:
        connectionSocket.close()
        return

    # proxy command parsing
    if path == "/proxy/cache/enable":
        info.caching = True
    elif path == "/proxy/cache/disable":
        info.caching = False
    elif path == "/proxy/cache/flush":
        cache.clear()
    elif path == "/proxy/blocklist/enable":
        info.blocking = True
    elif path == "/proxy/blocklist/disable":
        info.blocking = False
    elif "/proxy/blocklist/add/" in path:
        print("adding " + path[21:])
        blocklist.append(path[21:])
    elif "/proxy/blocklist/remove/" in path:
        print("removing " + path[24:])
        blocklist.remove(path[24:])
    elif path == "/proxy/blocklist/flush":
        try:
            print("flush blocklist")
            blocklist.clear()
        except OSError as e:
            print("blocklist was already empty")
    else:

        # check if host url is in blocked list if so then send error 403 and set blocked to true so we don't request from server
        blocked = False
        for n in blocklist:
            temp = n
            if(":" in n):
                temp = n.split(':')[0]
            if(temp in url and info.blocking):
                print('here')
                send_error(403, connectionSocket)
                blocked = True

        if(not blocked and sendRequest != "False"):#contine to send the response if the sendrequest wasn't false  
            response = b''
            key = url+path#key to the cache location of the cached website
            if(inCache(key) and info.caching):
                with lock:
                    # sendRequest = f"GET {path} HTTP/1.0\r\nHost: {url}{headers}\r\n"
                    date = cache[key][1][6:]
                conditionalRequest = f"{sendRequest}If-Modified-Since: {date}\r\nConnection: close\r\n\r\n"#make the request a conditional request by appending the correct header

                response = send_to_server(conditionalRequest, url, sendPort)#send the request and get the response 
                #check if the cache is out of date
                if(out_of_date(response)):
                    with lock:  # save the response to a file.
                        save_to_file(url, response)
                    # save file to cache
                    for x in response.splitlines():
                        if(b'Date: ' in x):
                            date = x.decode()
                            break

                    with lock:#add file to cache
                        cache[key] = (url, date)
                    connectionSocket.send(response)
                else:
                    #read the file and send it to user
                    with lock:
                        content = read_from_file(url)
                    connectionSocket.send(content)

            else:#if caching is off or the site wasn't in the cache
                sendRequest = sendRequest + "Connection: close\r\n\r\n"
                try:
                    response = send_to_server(sendRequest, url, sendPort)
                except Exception as e:
                    connectionSocket.close()
                    print("couldn't connect, socket closed")

                if(info.caching):
                    with lock:  # save the response to a file.
                        save_to_file(url, response)
                    # save file to cache
                    for x in response.splitlines():
                        if(b'Date: ' in x):
                            date = x.decode()
                            break

                    with lock:  # place response and date into cache
                        cache[key] = (url, date)
                
                connectionSocket.send(response)

    connectionSocket.close()


# Start of program execution
# Parse out the command line server address and port number to listen to
parser = OptionParser()
parser.add_option('-p', type='int', dest='serverPort')
parser.add_option('-a', type='string', dest='serverAddress')
(options, args) = parser.parse_args()

port = options.serverPort
address = options.serverAddress
if address is None:
    address = 'localhost'
if port is None:
    port = 2100


# Set up signal handling (ctrl-c)
signal.signal(signal.SIGINT, ctrl_c_pressed)

# TODO: Set up sockets to receive requests

# make the the tcp server socket
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
serverSocket.bind((address, port))
serverSocket.listen(1)

threadCount = 0

while True:
    connectionSocket, addr = serverSocket.accept()  # receives connection
    print('Connected to: ' + addr[0] + ':' + str(address[1]))
    start_new_thread(client_request, (connectionSocket, ))
    threadCount += 1
    print('Thread Number: ' + str(threadCount))
