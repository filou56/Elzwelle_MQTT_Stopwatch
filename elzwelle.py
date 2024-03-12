# Feb 2020 mit 2to3 nach Python3.
# händisch alle s.wfile.write("</body></html>")
#    ersetzt durch s.wfile.write(bytes("</body></html>", "utf-8"))  usw.

# Kurze Impulse werden in dieser Software-Version nicht unterdrueckt !!
# Auch nach unterdrueckten kurzen Impulsen schlaegt die Totzeit 200ms zu!
# Gefahr dass dann gar kein Zeitereignis ausgeloest wird

# Totzeit  nach einem Ereignis von 300 ms     durch bouncetime=300

# Software-Pull-Up Widerstaende am GPIO Eingang deakiviert wg RC-Glied
# zur Unterdrueckung kurzer Impulse

# Web-Browser mit den Zeiten wird alle 10 Sekunden automatisch aktualisiert

import time
#from time import sleep
import socket
import http.server
import platform
import threading
import tkinter
import os
import serial
import configparser
import googlesheet
import gc
import uuid
import paho.mqtt.client as paho

from   paho import mqtt
from   pathlib import Path

# import linecache
# import tracemalloc
#
# import sys
# from pympler.asizeof import asizeof
#
# def display_top(snapshot, key_type='lineno', limit=10):
#     snapshot = snapshot.filter_traces((
#         tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
#         tracemalloc.Filter(False, "<unknown>"),
#     ))
#     top_stats = snapshot.statistics(key_type)
#
#     print("Top %s lines" % limit)
#     for index, stat in enumerate(top_stats[:limit], 1):
#         frame = stat.traceback[0]
#         print("#%s: %s:%s: %.1f KiB"
#               % (index, frame.filename, frame.lineno, stat.size / 1024))
#         line = linecache.getline(frame.filename, frame.lineno).strip()
#         if line:
#             print('    %s' % line)
#
#     other = top_stats[limit:]
#     if other:
#         size = sum(stat.size for stat in other)
#         print("%s other: %.1f KiB" % (len(other), size / 1024))
#     total = sum(stat.size for stat in top_stats)
#     print("Total allocated size: %.1f KiB" % (total / 1024))


#from googlesheet import Spreadsheet, client_secret_file

#import RPi.GPIO as GPIO

# Google Spreadsheet ID for publishing times
# Elzwelle SPREADSHEET_ID = '1obtfHymwPSGoGoROUialryeGiMJ1vkEUWL_Gze_hyfk'
# FilouWelle spreadsheet_xxx, err := service.FetchSpreadsheet("1M05W0igR6stS4UBPfbe7-MFx0qoe5w6ktWAcLVCDZTE")
SPREADSHEET_ID = '1M05W0igR6stS4UBPfbe7-MFx0qoe5w6ktWAcLVCDZTE'

#CLIENT_SECRET_JSON = 'client_secret.json'

# How many time stamps should be stored and shown on the web page
KEEP_NUM_TIME_STAMPS = 20

# 10.02.2018 HM
NUMBER_OF_EVENT = 300

# define length for shortest pulse in seconds
#IGNORE_PULSE_LENGTH_SEC = 0.05

# GPIO pins for start and stop sensor
START_GPIO_PIN  = 20
FINISH_GPIO_PIN = 21

# Port number for the web server
PORT_NUMBER = 8080 # Maybe set this to 9000.

# host name (or IP address) for the web server
# copy-paste from the internet
# TODO: do not crash when network is unreachable.
HOST_NAME = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]

# some global variables
program_launch_time_stamp = float(int(time.time()))

time_stamps_start  = [program_launch_time_stamp] * KEEP_NUM_TIME_STAMPS
time_stamps_finish = [program_launch_time_stamp] * KEEP_NUM_TIME_STAMPS

# 12.01.2024 WF
time_stamps_start_dirty  = True
time_stamps_finish_dirty = True

update_time_stamp        = False
serial_time_stamp        = 0

serial_time_stamp_start  = 0
serial_time_stamp_finish = 0

# 10.02.2018 HM
time_stamps_start_all  = [program_launch_time_stamp] * NUMBER_OF_EVENT
time_stamps_finish_all = [program_launch_time_stamp] * NUMBER_OF_EVENT

# For publishing times in Google spreadsheet_xxx
#start_sheet  = Spreadsheet(spreadsheet_id=SPREADSHEET_ID, tab_name='Start')
#finish_sheet = Spreadsheet(spreadsheet_id=SPREADSHEET_ID, tab_name='Ziel')

#-------------------------------------------------------------------
# callback function when start sensor is triggered
# will be connected to an interrupt -- so runs in a different thread
#-------------------------------------------------------------------
def start_sensor_triggered(channel):
    global time_stamps_start_dirty 
    global serial_time_stamp_start
    
    if serial_time_stamp_start == 0:
        t = time.time()
    else:
        t = serial_time_stamp_start
        serial_time_stamp_start = 0
        
    # da war von Olaf eine Routine zur Unterdrueckung kurzer Impulse. Geloescht weil es nicht richtig funktioniert hat
    t2 = t - program_launch_time_stamp
    print(("adding start timestamp: {:.2f} ".format(t2)))
    time_stamps_start.insert(0, t)
    while( len(time_stamps_start) > KEEP_NUM_TIME_STAMPS):
        time_stamps_start.pop()
    # # 10.02.2018 HM
    time_stamps_start_all.insert(0, t)
    while( len(time_stamps_start_all) > NUMBER_OF_EVENT):
        time_stamps_start_all.pop()
    start_sheet.add_entry([time.strftime('%H:%M:%S', time.localtime(t)), t2])
    
    if config.getboolean('mqtt', 'enabled'):
        mqtt_client.publish("elzwelle/stopwatch/start", 
                            payload=time.strftime('%H:%M:%S', time.localtime(t)) 
                            + " {:.2f} 0".format(t2).replace(".",","), 
                            qos=1)
    time_stamps_start_dirty = True
    # print ("sys.getsizeof(klist1): ",sys.getsizeof(time_stamps_start_all))
    # print ("asizeof(klist1): ",asizeof(time_stamps_start_all))
#-------------------------------------------------------------------
# callback function when finish sensor is triggered
# will be connected to an interrupt -- so runs in a different thread
#-------------------------------------------------------------------
def finish_sensor_triggered(channel):
    global time_stamps_finish_dirty
    global serial_time_stamp_finish
    
    if serial_time_stamp_finish == 0:
        t = time.time()
    else:
        t = serial_time_stamp_finish
        serial_time_stamp_finish = 0
        
    # wait if signal disappears too early -- removed
    t2 = t - program_launch_time_stamp
    print(("adding finish timestamp: {:.2f} ".format(t2)))
    time_stamps_finish.insert(0, t)
    while( len(time_stamps_finish) > KEEP_NUM_TIME_STAMPS):
        time_stamps_finish.pop()
    # # 10.02.2018 HM
    time_stamps_finish_all.insert(0, t)
    while( len(time_stamps_finish_all) > NUMBER_OF_EVENT):
        time_stamps_finish_all.pop()
    finish_sheet.add_entry([time.strftime('%H:%M:%S', time.localtime(t)), t2])
    if config.getboolean('mqtt', 'enabled'):
        mqtt_client.publish("elzwelle/stopwatch/finish", 
                            payload=time.strftime('%H:%M:%S', time.localtime(t)) 
                            + " {:.2f} 0".format(t2).replace(".",","), 
                            qos=1)
    time_stamps_finish_dirty = True


#-------------------------------------------------------------------
# This is the webserver.
#-------------------------------------------------------------------
class MyHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    def do_GET(self):
        """Respond to a GET request."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        if self.path == "/start":
            # web page for start time stamps
            # Zusatz von Joerg mit autom. Aktualisierung vom 18.03.2017 funktioniert
            # aber beim Aktualisieren wird Markierung fuer copy/paste geloescht!!
            # Deshalb wird nur alle 10 Sekunden aktualisiert
            self.wfile.write(bytes("<html><head><title>Start Zeitstempel</title><meta http-equiv=\"refresh\" content=\"10\" /></head>", "utf-8"))
            # s.wfile.write("<html><head><title>Start Zeitstempel</title></head>")
            self.wfile.write(bytes("<body><h1>Start Zeitstempel (aktualisiert {})</h1>".format(time.strftime("%H:%M:%S")), "utf-8"))
            for t in time_stamps_start:
                t2 = t - program_launch_time_stamp
                self.wfile.write(bytes("{:.2f}<br>".format(t2).replace(".",","), "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))
        elif self.path == "/ziel":
            # web page for finish time stamps
            # <meta http-equiv=\"refresh\" content=\"10\" />
            self.wfile.write(bytes("<html><head><title>Ziel Zeitstempel</title><meta http-equiv=\"refresh\" content=\"10\" /></head>", "utf-8"))
            self.wfile.write(bytes("<body><h1>Ziel Zeitstempel (aktualisiert {})</h1>".format(time.strftime("%H:%M:%S")), "utf-8"))
            for t in time_stamps_finish:
                t2 = t - program_launch_time_stamp
                self.wfile.write(bytes("{:.2f}<br>".format(t2).replace(".",","), "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

            # 10.02.2018 HM start_all und ziel_all eingefuegt
        elif self.path == "/start_all":
            # web page for ALL start time stamps
            # <meta http-equiv=\"refresh\" content=\"10\" />
            self.wfile.write(bytes("<html><head><title>Alle Start Zeitstempel</title></head>", "utf-8"))
            self.wfile.write(bytes("<body><h1>Alle Start Zeitstempel (aktualisiert {})</h1>".format(time.strftime("%H:%M:%S")), "utf-8"))
            for t in time_stamps_start_all:
                t2 = t - program_launch_time_stamp
                self.wfile.write(bytes("{:.2f}<br>".format(t2).replace(".",","), "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

        elif self.path == "/ziel_all":
            # web page for ALL finish time stamps
            # <meta http-equiv=\"refresh\" content=\"10\" />
            self.wfile.write(bytes("<html><head><title>Alle Ziel Zeitstempel</title></head>", "utf-8"))
            self.wfile.write(bytes("<body><h1>Alle Ziel Zeitstempel (aktualisiert {})</h1>".format(time.strftime("%H:%M:%S")), "utf-8"))
            for t in time_stamps_finish_all:
                t2 = t - program_launch_time_stamp
                self.wfile.write(bytes("{:.2f}<br>".format(t2).replace(".",","), "utf-8"))
            self.wfile.writ(bytes("</body></html>", "utf-8"))


        else:
            # standard webpage for everything else
            self.wfile.write(bytes("<html><head><title>Elzslalom</title></head>", "utf-8"))
            self.wfile.write(bytes("<body><h1>Elzslalom</h1>", "utf-8"))
            self.wfile.write(bytes("<ul><li><a href='/start'>Zeitstempel Start</a></li>", "Utf-8"))
            self.wfile.write(bytes("<li><a href='/ziel'>Zeitstempel Ziel</a></li></ul>", "utf-8"))
            #10.02.2018 HM  start_all und ziel_all eingefuegt
            self.wfile.write(bytes("<li><a href='/start_all'>Zeitstempel Start alle</a></li>", "utf-8"))
            self.wfile.write(bytes("<li><a href='/ziel_all'>Zeitstempel Ziel alle</a></li></ul>", "utf-8"))

            self.wfile.write(bytes("</body></html>", "utf-8"))

#-------------------------------------------------------------------
# Define the GUI
#-------------------------------------------------------------------
class simpleapp_tk(tkinter.Tk):
    def __init__(self,parent):
        tkinter.Tk.__init__(self,parent)
        self.parent = parent
        self.initialize()

    def initialize(self):
        self.grid()

        #Add a label with the text leftbound black font(fg) on white background(bg) at (0,0) over 2 columns,
        #sticking to the left and to the right of the cell
        self.labelVariable = tkinter.StringVar()
        label = tkinter.Label(self,textvariable=self.labelVariable,anchor="w",fg="black",bg="white")
        label.grid(row=0,column=0,columnspan=2,sticky="EW")
        self.labelVariable.set(HOST_NAME)

        #Add a button that says 'Start' at (1,0)
        button1 = tkinter.Button(self,text="Start",command=self.StartButtonClicked)
        button1.grid(row=1,column=0,sticky="EW")

        #Add a button that says 'Ziel' at (1,1)
        button2 = tkinter.Button(self,text="Ziel",command=self.FinishButtonClicked)
        button2.grid(row=1,column=1,sticky="EW")

        self.startTimeStampsMessage = tkinter.Message(self,text="",
                                                      relief=tkinter.SUNKEN,
                                                      font='TkFixedFont')
        self.startTimeStampsMessage.grid(row=2,column=0,sticky="EW")
        
        self.finishTimeStampsMessage = tkinter.Message(self,text="",
                                                       relief=tkinter.SUNKEN,
                                                       font='TkFixedFont')
        self.finishTimeStampsMessage.grid(row=2,column=1,sticky="EW")

        #Make the first column (0) resize when window is resized horizontally
        self.grid_columnconfigure(0,weight=1)
        self.grid_columnconfigure(1,weight=1)

        #Make the user only being able to resize the window horrizontally
        self.resizable(True,True)

    def StartButtonClicked(self):
        start_sensor_triggered(None)

    def FinishButtonClicked(self):
        finish_sensor_triggered(None)

    def OnPressEnter(self,event):
        self.labelVariable.set (self.entryVariable.get()+"(You pressed ENTER!)")

    def refresh(self):
        global time_stamps_start_dirty 
        global time_stamps_finish_dirty
        global update_time_stamp
        global serial_time_stamp
        
        if update_time_stamp or not config.getboolean('serial', 'enabled'):
            #self.labelVariable.set(serial_time_stamp)
            if serial_time_stamp == 0:
                t = time.time()
            else:
                t = serial_time_stamp
                
            self.labelVariable.set("{} | {} | ".format(HOST_NAME, time.strftime("%H:%M:%S"))+
                                   "{:.2f}".format(t-program_launch_time_stamp).replace(".",","))
            update_time_stamp = False
            #self.labelVariable.set("{} ({}): {:.2f}".format(HOST_NAME, time.strftime("%H:%M:%S"), time.time()-program_launch_time_stamp))
        # elif not config.getboolean('serial', 'enabled'):
        #     t = time.time() 
        #     self.labelVariable.set("{} | {} | ".format(HOST_NAME, time.strftime("%H:%M:%S"))+
        #                            "{:10.2f}".format(t-program_launch_time_stamp).replace(".",","))
        if time_stamps_start_dirty:
            message = ""
            for t in time_stamps_start:
                t2 = t - program_launch_time_stamp
                message += time.strftime("%H:%M:%S | ",time.localtime(t)) + "{:10.2f}\n".format(t2).replace(".",",")
            self.startTimeStampsMessage.config(text=message) # TODO Filou
            time_stamps_start_dirty = False

        if time_stamps_finish_dirty:
            message = ""
            for t in time_stamps_finish:
                t2 = t - program_launch_time_stamp
                message += time.strftime("%H:%M:%S | ",time.localtime(t)) + "{:10.2f}\n".format(t2).replace(".",",")
            self.finishTimeStampsMessage.config(text=message) # TODO Filou
            time_stamps_finish_dirty = False
              
#        snapshot = tracemalloc.take_snapshot()
#        display_top(snapshot)
        
#        print("GC: ",gc.collect())
        gc.collect()
        self.after(500, self.refresh)

#-------------------------------------------------------------------

# setting callbacks for different events to see if it works, print the message etc.
def on_connect(client, userdata, flags, rc, properties=None):
    """
        Prints the result of the connection with a reasoncode to stdout ( used as callback for connect )

        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param flags: these are response flags sent by the broker
        :param rc: stands for reasonCode, which is a code for the connection result
        :param properties: can be used in MQTTv5, but is optional
    """
    print("CONNACK received with code %s." % rc)
        
    # subscribe to all topics of encyclopedia by using the wildcard "#"
    client.subscribe("elzwelle/stopwatch/#", qos=1)
    
    # a single publish, this can also be done in loops, etc.
    client.publish("elzwelle/monitor", payload="running", qos=1)
    

FIRST_RECONNECT_DELAY   = 1
RECONNECT_RATE          = 2
MAX_RECONNECT_COUNT     = 12
MAX_RECONNECT_DELAY     = 60

def on_disconnect(client, userdata, rc):
    print("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        print("Reconnecting in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            print("Reconnected successfully!")
            return
        except Exception as err:
            print("%s. Reconnect failed. Retrying...", err)

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    print("Reconnect failed after %s attempts. Exiting...", reconnect_count)


# with this callback you can see if your publish was successful
def on_publish(client, userdata, mid, properties=None):
    """
        Prints mid to stdout to reassure a successful publish ( used as callback for publish )

        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param properties: can be used in MQTTv5, but is optional
    """
    print("Publish: mid: " + str(mid))


# print which topic was subscribed to
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """
        Prints a reassurance for successfully subscribing

        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param granted_qos: this is the qos that you declare when subscribing, use the same one for publishing
        :param properties: can be used in MQTTv5, but is optional
    """
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


# print message, useful for checking if it was successful
def on_message(client, userdata, msg):
    """
        Prints a mqtt message to stdout ( used as callback for subscribe )

        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param msg: the message with topic and payload
    """
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    
#---------------------- End MQTT Callbacks ---------------------------------

#-------------------------------------------------------------------
# Main program
#-------------------------------------------------------------------
if __name__ == '__main__':    
    GPIO = None
   
    #gc.set_debug(gc.DEBUG_LEAK)
   
    myPlatform = platform.system()
    print("OS in my system : ", myPlatform)
    myArch = platform.machine()
    print("ARCH in my system : ", myArch)

    config = configparser.ConfigParser()
    # Defaults Linux Raspberry Pi
    config['serial'] = {'enabled':'no',
                        'port':'/dev/ttyUSB1',
                        'baud':'57600',
                        'timeout':'10'}
    
    config['http']   = {'port':PORT_NUMBER,
                        'enabled':'true'}
    
    config['google'] = {'spreadsheet_id':SPREADSHEET_ID}
    
    config['gpio']   = {'enabled':'no',
                        'start_gpio_pin':START_GPIO_PIN,
                        'finish_gpio_pin':FINISH_GPIO_PIN,
                        'bouncetime':300
                        }
    
    config['mqtt']   = {'enabled':'no'}
    
    # Platform specific
    if myPlatform == 'Windows':
        # Platform defaults
        config['serial']['port'] = 'COM4'
        config.read('windows.ini') 
    if myPlatform == 'Linux':
        config.read('linux.ini')

    try:
        googlesheet.client_secret_file = config.get('google', 'client_secret_json')
        if googlesheet.client_secret_file.startswith(".elzwelle"):
            home_dir = Path.home()
            print( f'Path: { home_dir } !' )
            googlesheet.client_secret_file = os.path.join(home_dir,googlesheet.client_secret_file)
        print("Setup GOOGLE: ",googlesheet.client_secret_file)
    except:
        print("Setup GOOGLE with defaults ")
    
    start_sheet  = googlesheet.Spreadsheet(spreadsheet_id=config.get('google', 'spreadsheet_id'), tab_name='Start')
    finish_sheet = googlesheet.Spreadsheet(spreadsheet_id=config.get('google', 'spreadsheet_id'), tab_name='Ziel')

    if config.getboolean('gpio', 'enabled'):
        if myPlatform == 'Linux' and myArch == 'armv6l':
            try:
                import RPi.GPIO as GPIO
            except ImportError:
                print('EXCEPTION: Import GPIO')
                os.abort()
            # Use GPIO numbers not pin numbers
            GPIO.setmode(GPIO.BCM)
        
            start_pin  = config.getint('gpio','start_gpio_pin')
            finish_pin = config.getint('gpio','finish_gpio_pin')
            bounce_pin = config.getint('gpio','bouncetime')
            # GPIO 20 and 21 set as inputs, interne pull-up Widerst. deaktiviert
            # To trigger an event, they must be pulled down to ground.
            GPIO.setup(start_pin, GPIO.IN)
            GPIO.setup(finish_pin, GPIO.IN)
        
            # setup an interupt handler for falling edge on GPIO 20 for start
            # sensor and GPIO 21 for finish sensor. Ignore further edges for 300ms
            # for switch bounce handling.
            GPIO.add_event_detect(start_pin, GPIO.FALLING,
                                  callback=start_sensor_triggered,
                                  bouncetime=bounce_pin)
            GPIO.add_event_detect(finish_pin, GPIO.FALLING,
                                  callback=finish_sensor_triggered,
                                  bouncetime=bounce_pin)
        else:
            print('ERROR GPIO: Not a Raspberry Py')
            
    if config.getboolean('http', 'enabled'):
        # setup and start webserver in separate thread
        server_class = http.server.HTTPServer
        httpd = server_class((HOST_NAME, config.getint('http', 'port')), MyHandler)
        print(time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, config.getint('http', 'port')))
        try:
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            print(time.asctime(), "Server is running")
        except KeyboardInterrupt:
            pass
        #print("It works! Version für Py3.7  Elz_2021_12_a.py  neu")
    #----------------------------End HTTP -----------------------------------------------
    
    if config.getboolean('serial', 'enabled'):
        
        # Initialize the port    
        serialPort = serial.Serial(config.get('serial', 'port'),
                               config.getint('serial', 'baud'), 
                               timeout=config.getint('serial', 'timeout'))
            
        # Function to call whenever there is data to be read
        def readFunc(port):
            global update_time_stamp
            global serial_time_stamp
            global serial_time_stamp_start
            global serial_time_stamp_finish
            global program_launch_time_stamp
             
            time.sleep(2)   
            print('Read RTC')
            port.write(str.encode('r'))  
            time.sleep(0.5)
            unix_epoch = int(program_launch_time_stamp) 
            print('Set Epoch: {0:d}'.format(unix_epoch))
            port.write(str.encode('e{0:d}'.format(unix_epoch)))      
                      
            while True:
                try:
                    line = port.readline().decode("utf-8")
                    if len(line) > 0:
                        if line[0] == '#':
                            try:
                                serial_time_stamp = float(line[1:-1])
                                update_time_stamp = True
                            except ValueError:
                                print("EXCEPTION serial_time_stamp:  Not a float")
                        else:
                            print('Cmd response: '+line[0:-1])
                        if line[0] == 'S':
                            try:
                                serial_time_stamp_start = float(line[1:-1])
                                print('Start {0:.2f}'.format(serial_time_stamp_start))
                                start_sensor_triggered(None)
                            except ValueError:
                                print("EXCEPTION serial_time_stamp_start:  Not a float")
                        if line[0] == 'F':
                            try:
                                serial_time_stamp_finish = float(line[1:-1])
                                print('Finish {0:.2f}'.format(serial_time_stamp_finish))
                                finish_sensor_triggered(None)
                            except ValueError:
                                print("EXCEPTION serial_time_stamp_finish:  Not a float")      
                except Exception as e:
                    print("EXCEPTION in readline: ",e) 
            
            print("DONE readline")
                           
        # Configure threading
        usbReader = threading.Thread(target = readFunc, args=[serialPort])
        usbReader.start()
    #-------------------------------End GPIO --------------------------------------------
    
    if config.getboolean('mqtt', 'enabled'):
        mqtt_client = paho.Client(client_id="elzwelle_"+str(uuid.uuid4()), userdata=None, protocol=paho.MQTTv311)
    
        # enable TLS for secure connection
        if config.getboolean('mqtt','tls_enabled'):
            mqtt_client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        # set username and password
        if config.getboolean('mqtt','auth_enabled'):
            mqtt_client.username_pw_set(config.get('mqtt','user'),
                                    config.get('mqtt','password'))
        # connect to HiveMQ Cloud on port 8883 (default for MQTT)
        mqtt_client.connect(config.get('mqtt','url'), config.getint('mqtt','port'))
       
        # setting callbacks, use separate functions like above for better visibility
        mqtt_client.on_connect      = on_connect
        mqtt_client.on_subscribe    = on_subscribe
        mqtt_client.on_message      = on_message
        mqtt_client.on_publish      = on_publish
        
        mqtt_client.loop_start()
        
        # subscribe to all topics of encyclopedia by using the wildcard "#"
        mqtt_client.subscribe("elzwelle/timestamp/#", qos=1)
        
        # a single publish, this can also be done in loops, etc.
        mqtt_client.publish("elzwelle/stoppwatch", payload="running", qos=1)
        #mqtt_client.loop_start()
    #-------------------------------- End MQTT -------------------------------------------
    
#    tracemalloc.start()
        
    # setup and start GUI
    app = simpleapp_tk(None)
    app.title("MQTT Stoppuhr Elz-Zeit")
    app.refresh()
    app.mainloop()
    print(time.asctime(), "GUI done")
    
    if config.getboolean('http', 'enabled'):
        httpd.server_close()
        print(time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, config.getint('http', 'port')))
        
    # Stop all dangling threads
    os.abort()
