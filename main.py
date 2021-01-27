import socket
import threading
import time
import os

def checksum(arr):
    sum = 0

    for i in range(1, len(arr)):
        sum += arr[i]
        while sum > 255:
            sum -= 254

    return sum


class Server:
    def __init__(self, ip, port):
        self.mySocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.headSize = 4
        self.bufferSize = 1472 - self.headSize
        self.ip = ip
        self.port = port

    def serv(self):
    # Bind to address and ip
        self.mySocket.bind((self.ip, self.port))
        print("UDP server up and listening")

        # Listen for incoming datagrams
        while True:
            temp = self.mySocket.recvfrom(self.bufferSize)
            message = temp[0]
            address = temp[1]
            
            replHeader = bytearray(self.headSize)
            if checksum(message) != message[0]:
                replHeader[2] = 0   #reply is one fragment
                replHeader[3] = 1
                replHeader[1] = 5   #indicates a mistake
                replHeader[0] = checksum(replHeader)    
                self.mySocket.sendto(replHeader, address)
                print("Recived packet corrupted, asking for new one.")
                continue

            counter = 1
            if(message[1] == 0):
                whole = ""
            elif message[1] == 1:
                whole = bytearray(0)
                filename = ""
            elif message[1] == 2:
                print("Recived keepalive")
                continue

            while counter <= (message[2] * 256 + message[3]):
                if counter != 1:
                    temp = self.mySocket.recvfrom(self.bufferSize)   
                message = temp[0]
                address = temp[1]

                if message[1] == 2:
                    print("Recived keepalive")
                    continue

                #Recieving fragments and checking their integrity
                print("Got fragment {} with size {} bytes".format(counter, len(message)))
                if checksum(message) != message[0]:
                    replHeader[2] = 0   #reply is one fragment
                    replHeader[3] = 1
                    replHeader[1] = 5   #indicates a mistake
                    replHeader[0] = checksum(replHeader)    
                    self.mySocket.sendto(replHeader, address)
                    print("Recived packet corrupted, asking for new one.")
                    continue
                else:
                    replHeader[2] = 0   #reply is one fragment
                    replHeader[3] = 1
                    replHeader[1] = 4   #indicates correct packet
                    replHeader[0] = checksum(replHeader)    
                    self.mySocket.sendto(replHeader, address)
                    print("Recived packet correctly.")

                if message[1] == 0:
                    whole += message[self.headSize:].decode()
                elif message[1] == 1:
                    if counter == 1:
                        filename += message[self.headSize:].decode()
                    else:
                        whole += message[self.headSize:]
                else:
                    print("Server shutting down")
                    return

                counter += 1



            if message[1] == 0:
                print("The  message is: {}".format(whole))
            elif message[1] == 1:
                open(filename, "wb").write(whole)
                print("File created at {2}\nAccepted {0} fragments\nFile size: {1} Bytes\n".format(message[2] * 256 + message[3], len(whole), os.getcwd() + "\\" + filename ))

class Client:
    def __init__(self, ip, port):
        self.mySocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.headSize = 4
        self.bufferSize = 1472 - self.headSize
        self.ip = ip
        self.port = port
        self.badTest = 1

    def sendPacket(self, message, ip, port):
        adrPort = (ip, port)
        # Send to server using created UDP socket
        self.mySocket.sendto(message, adrPort)

    def keepalive(self):
        while True:
            time.sleep(60)
            toSend = bytearray(self.headSize)
            toSend[1] = 2
            toSend[2] = 255
            toSend[3] = 255
            toSend[0] = checksum(toSend)

            self.sendPacket(toSend,self.ip, self.port)
            print("Sent keepalive")

    def clint(self):
        kind = 1
        keepThread = threading.Thread(target=self.keepalive)
        keepThread.daemon = True
        while True:
            #parameters of message sent by client
            kind = int(input("\n0-text\n1-file\n3-end\nother-kill server\n"))
            if kind == 3:
                return

            fragLen = int(input("Input max fragment length:\n"))
            if(fragLen > self.bufferSize):
                fragLen = self.bufferSize
                print("Fragment size bigger than possible cap, setting to 1472.")

            if kind == 0:
                message = input("Input message:\n").encode()
            elif kind == 1:
                fileName = input("Input name of file:\n")
                message = open(fileName, "rb").read()
            elif kind == 3:
                return
            else:
                message = "Foo".encode()

            mesLen = len(message)

            #Creating header
            header = bytearray(self.headSize)
            header[0] = 0   #checksum
            header[1] = kind   #message Type
            numOfFrags = len(message)//(fragLen - self.headSize) + (len(message)%(fragLen - self.headSize) > 0) + kind
            header[2] = (numOfFrags & 65280) >> 8
            header[3] = numOfFrags & 255

            #If we are sending a file, first fragment will be filename
            if kind == 1:
                header[0] = checksum(header + fileName.encode())
                self.sendPacket(header + fileName.encode(), self.ip, self.port)
                repl = self.mySocket.recvfrom(self.bufferSize)
                if repl[0][1] == 4:
                    print("Message was sent succesfully")
                elif repl[0][1] == 5:
                    print("Fragment corrupted")
                    while repl[0][1] != 4:
                        header[0] = checksum(header + fileName.encode())
                        self.sendPacket(header + fileName.encode(), self.ip, self.port)
                        repl = self.mySocket.recvfrom(self.bufferSize)

            beg = 0
            end = fragLen - self.headSize
            while not(end >= (mesLen + fragLen - self.headSize)):
                toSend = header + message[beg:end]
                toSend[0] = checksum(toSend)
                #Test bad frag
                if self.badTest == 1:
                    self.badTest = 0
                    toSend[1] = 90
                self.sendPacket(toSend, self.ip, self.port)
                repl = self.mySocket.recvfrom(self.bufferSize)
                if repl[0][1] == 4:
                    print("Message was sent succesfully")
                elif repl[0][1] == 5:
                    print("Fragment corrupted")
                    continue
                beg += fragLen - self.headSize
                end += fragLen - self.headSize
                
            if not(keepThread.is_alive()):
                keepThread.start()
            

ip = input("Input ip:\n") #"127.0.0.1"
servPort = int(input("Input server port:\n"))
clientPort = int(input("Input client port:\n"))


server = Server(ip, servPort)
client = Client(ip, clientPort)

x = threading.Thread(target=server.serv)
x.start()
print("server running")

y = threading.Thread(target=client.clint)
y.start()

print("Client running")