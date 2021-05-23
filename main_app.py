#!/usr/bin/python

import threading
from threading import Thread
import cantools
import can
import sys, getopt
import csv
import os
import time
from collections import OrderedDict
from datetime import datetime

#------------------------------
#GLOBALS
#used by k15 off in order to stop all messages, (it works like a semaphore)
stop_bus = threading.Event()

#used to have a cleaner stdout
wait_to_stdout = threading.Event() 

#dictionary of threading.Event() used by user at runtime to pause/resume writing threads, key=msg_name,value=.Event() obj
keep_running = {} 

GPIO_PRESENT = True
#GPIO input pin = 23
#------------------------------

try:
    import RPi.GPIO as GPIO
except ImportError:
    #GPIO hardware not usable
    print(sys.exc_info())
    GPIO_PRESENT = False
    
"""
**INFO:
    -inits the 'keep_running' data structure (dictionary for obj: threading.Event())
**PARAMETERS:
    -current: dictionary that map all current messages (num threads) that are running key=index,value=msg_name
    -all: dictionary that map all messages (num threads) that can be run. key=index,value=msg_name
        both dictionary comes from map() function
"""
        
def init_block_events(currents,all):
    for message in all.values():
        keep_running[message] = threading.Event()
        if message in currents.values():
            #message willing to run
            keep_running[message].set()
        else:
            #message set to idle
            keep_running[message].clear()
        
"""
support function for thread_event_block().
**PARAMETERS:
    -msg_name = can message name (->thread) that user want to pause/resume
**INFO:
    -returns 1 if keep_running is set
    -return 2 if keep_running is cleared
    -return 3 if nothing appens
"""

def set_thread_event_block(msg_name):
    if not keep_running[msg_name].isSet():
        keep_running[msg_name].set()
        return int(1)
    else:
        keep_running[msg_name].clear()
        return int(2)
    return int(3)

"""
thread used for syncronization between all others thread
**INFO:
    -used in order to allow user to pause/resume a writing thread at runtime or start a new one
    -it makes use of global variable keep_running{}
    -if user wants to stop thread number 3, just need to tipe '3' on screen and the thread will be blocked
        or resumed if previously blocked
        or started if not previously started
    -blocked by threading.Event() object set to False by systemcall .clear()
    -thread stay in blocked state until user resume it by re-tiping same index (for ex the previous'3')
    -resumed by threading.Event() object set to True by systemcall .set()
**PARAMETERS:
    -current: dictionary that map all current messages (num threads) that are running key=index,value=msg_name
    -all: dictionary that map all messages (num threads) that can be run. key=index,value=msg_name
        both dictionary comes from map() function
    -bus_wr,db,get_timestamp_from_file: parameters to give at the writeOnBus() function
"""
        
def thread_event_block(current,all,bus_wr,timing,db,get_timestamp_from_file):
    new_writer = []
    print("\ny are allowed to stop/resume a thread, by typing his index")
    print("use the LINKS MAP to see correct linking\n")
    print("if you want to replay a new message that you did not choose before")
    print("use the CAN MAP to see correct indexing")
    print("WARNING index -1 is like a k15 off but with an immediate termination\n")
    selectable = int(len(all))
    new_added = 0
    while True:
        if stop_bus.isSet():
            print("k15 signal is off, bus is shutdown now")
            #all signals are now reactiveted due to a correct exit :)
            for msg_name in current.values():
                if not keep_running[msg_name].isSet():
                    keep_running[msg_name].set()
            for i in range(0,new_added):
                new_writer[i].join()
            break
        try:
            wait_to_stdout.clear()
            l = int(input("> "))
            if l < -1 or l >= selectable:
                raise ValueError
            if l == -1:
                print("ok i stop the program")
                stop_bus.set()
                continue
        except:
            sys.stderr.write("wrong value\n")
            continue
        if l in current.keys():
            if set_thread_event_block(current[l]) == 3:
                continue
        elif l in all.keys():
            print("NEW ENTRY ON LINKS MAP")
            print("___________________________")
            message = all[l]
            new_writer.append(threading.Thread(target=writeOnBus, args=("WRITER_"+str(message),bus_wr.state,bus_wr,message,timing,db,get_timestamp_from_file)))
            new_writer[new_added].start()
            print("message: "+str(message)+" linked to index " +str(l))
            print("___________________________")
            new_added += 1
            current[l] = message
            if set_thread_event_block(message) == 3:
                continue
            wait_to_stdout.set()
        wait_to_stdout.wait()

"""
**INFO:
    -Thread that listen on k15 signal, if k15 go off this
    -thread allows can message to be sent only for 8 s more.
"""

def K15listener():
    while True:
        if GPIO.input(23) == False:
            print("K15 off, you have 8 seconds left")
            time.sleep(8)
            stop_bus.set()
            break
        time.sleep(0.01)
    #used to make a clean exit by thread_event_block()
    if not wait_to_stdout.isSet():
        wait_to_stdout.set()
        print("\n_____press a key to exit_____\n")
    
"""
*Thread for diagnostic message
**INFO:
    -encode a diagnostic message, identified by frame_id, from db (.dbc)
    -if k15 goes off, this thread exits
    -if threading.Event() associated to this thread is detected, this thread goes in waiting/resuming
"""
            
def diagnosticRQ(nome,description,bus,db,frame_id):
    #print(nome,description)
    message = db.get_message_by_frame_id(frame_id)
    encoded = message.encode({'N_PDU': 1})
    to_send = can.Message(arbitration_id=message.frame_id,data=encoded)
    count = 0
    while True:
        if stop_bus.isSet():
            print("k15 signal off, threading.event() detected")
            break
        if keep_running[message.name].isSet():
            bus.send(to_send)
            count += 1
            time.sleep(0.01)
        else:
            print("pause event detected")
            print("Processed "+str(count)+" signals for file "+str(message.name))
            wait_to_stdout.set()
            keep_running[message.name].wait()
            print("play event detected, resuming "+str(message.name))
            wait_to_stdout.set()
    print("Processed "+str(count)+" for diagnostic "+str(message.name))

def addMessageToDict(running,all,db,frame_id_1):
    message_obj = db.get_message_by_frame_id(frame_id_1)
    message = str(message_obj.name)
    running[len(all)] = message
    all[len(all)] = message
    return all,message

"""
*wrapper for replay() function
**PARAMETERS:
    -name: thread name, just used for stdout verbose
    -description: a brief thread description, just for stdout verbose
    -bus: socket where messages are written
    -timing: sending period in milliseconds
    -db: dbc for encoding
    -flag: used by the replay_log.__write__() function
**INFO:
    -needs a socket for writing that must be different from reading one
    -retrive message_data_structure from given database
    -print some info about message_data_structure
"""

def writeOnBus(nome,description,bus,message,timing,db,flag):
    #print (nome,description)
    #message name --> database --> message data structure 
    message_to_send = db.get_message_by_name(str(message))  
    current_bit_rate = message_to_send.length * 8 *timing
    #print("bitrate in transmission "+str(current_bit_rate)+" message: "+str(message_to_send.name))
    #print("message structure\n"+str(message_to_send.layout_string(signal_names=True))+" message: "+str(message_to_send.name))
    replay(bus,message_to_send,timing,db,flag)
    #print(nome+" Terminated")
         
"""
*Thread that implemets a candump OUTPUT='date_time'.log
**PARAMETERS:
    -name: thread name, just used for stdout verbose
    -description: a brief thread description, just for stdout verbose
    -bus: socket where messages are read
    -timing: sending period in milliseconds
    -db: dbc for encoding
**INFO:
    -needs a socketbus for reading that must be different from socketbus for writing
    -uses the .recv() funtion without timeout so the thread will stay in busy waiting until something appen on the bus
    -whenever recives a message from socket, if the massage is a part of the database it will be decoded
    -it stops whenever k15 signal goes off
"""

def dump(file_name,bus):
    count = 0
    try:
        fd = open(str(file_name),'w')
        while True:
            if stop_bus.isSet():
                print("k15 off, dump completed")
                print("dumped "+str(count)+" messages")
                break
            msg=bus.recv()
            count += 1
            fd.write(str(msg)+'\n')
        fd.close()
        print("dump terminated")
    except:
        sys.stderr.write("ERROR ON dump")
        sys.stderr.write(sys.exc_info())
    finally:
        if fd != None:
            fd.close()
                
"""
**INFO:
    -this function allow y to select one database from the list returned by searcher() function
"""

def load_db():
    dbcs,dim = searcher('DBCS','.dbc')
    print("DBC MAP")
    print("___________________________")
    print("you can select one dbs, please select by index")
    for i in range(dim):
        print(str(i)+" "+str(dbcs[i]))
    print("___________________________")
    try:
        l = int(input("> "))
    except:
        sys.stderr.write("ERROR ON DB_LOAD")
        print(sys.exc_info())
        exit()
    if (l >= dim) or (l<0) :
        print("input not correct!")
        exit()
    return dbcs[l]

"""
*search function
**PARAMETERS:
    -dir: directory path to discover 
    -fil: format file to discover (.csv)
**INFO:
    -dir must be in script directory
    -this function will only list files with .'$fil' format
    -returs a list of file names (ex: a list of .csv files or a list of .dbc files..)
"""

def searcher(dir,fil):
    try:
        SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
        _DIR_PATH=os.path.join(SCRIPT_DIR,dir)
        founds = []
        i=0
        for file in os.listdir(_DIR_PATH):
            if file.endswith(fil):
                founds.append(file)
                i+=1
        if (len(founds) == 0):
            print("empty directory!")
            exit()
    except:
        sys.stderr.write("ERROR ON SEARCHER")
        print(sys.exc_info())
        exit()
    return founds,i
   
"""
*mapping function that allow y to select one or more .csv logs to replay as can messages
**PARAMETERS:
    -database: dbc database for encoding and decoding can messages
**INFO:
    -all logs must be in "LOGS" directory in order to be listed
    -in order to be reconized, all logs must be messages in in the dbc selected before
    -csv name = can message 
    -csv name not in dbc database = message not reconized = program wont send it
    -'logs' is a dictionary filled with all csv files found in 'LOGS' directory index,msg_name
    -'dict' is dictionary filled with all messages that u are allowed to send (reconized) index,msg_name
"""

def map(database):
    logs,tmp = searcher('LOGS','.csv')
    i = 0
    k = 0
    dict=OrderedDict()
    sel = OrderedDict()
    for file in logs:
        for mes in database.messages:
            temp_name = file.split('.')
            if mes.name == temp_name[0]:
                #this log file (can message) exists in the db
                dict[i] = ""
                dict[i] = (mes.name)
                i += 1
                break
    print("CAN MAP")
    print("___________________________")
    for key,value in dict.items():
        print(key,value)
    print("___________________________")
    print("you can replay theese messages, please select one or more by tiping indexes, out of range = no more, -1 == all selected")
    while (k < i): #y can select max i messages
        try:
            l = int(input("> "))
        except:
            sys.stderr.write("ERROR ON MAPPING")
            sys.stderr.write(sys.exc_info())
            exit()
        if l == -1:
            #all listed messages will be replayed
            for key,value in dict.items():
                sel[key] = value
            return sel,dict
        if (l < i) and (l >= 0):
            sel[l] = ""
            sel[l]=(dict.get(l))
            k += 1
        else:
            break
    for key,value in sel.items():
        print(key,value)
    return sel,dict

"""
*this function lunches n writer threads for each log file selected to be replayed
**PARAMETERS:
    -argv: command line args
        -if args is None program uses default parameters showed below
            -no verbose on stdout (reading from can bus is disabled)
            -sockets uses virtual can named 'vcan0'
            -each can message is replayed with 1000 ms timing
            -no diagnostic messages (diagnostic_id_)are sended
            -gpio k15 in enabled (if machine has pinout hardware)
    -GPIO_PRESENT: flag for GPIO fucntionality, if False --> machine doesn't support gpio
**INFO:
    -read args for settings
    -initialize sockets for reading and writing on can interface
    -can interface must be on, check ifconfig to see if interface is UP,RUNNING
    -launch a thread for each message to replay on can bus with
"""

def _startup_(argv,GPIO_PRESENT):
   
    #----------------
    #default settings
    _CHANNEL_ = 'vcan0'
    _BUSTYPE_ = 'socketcan'
    verbosity = False
    timing = 1
    get_timestamp_from_file = True
    diagnostic = False
    diagnostic_id_1 = 0x18DA10F1
    diagnostic_id_2 = 0x18DBFEF1
    #----------------
    threads = 0
    writer = []
    file_name = ""
    blocking = None
    diagnostic_name_1 = ""
    diagnostic_name_2 = ""
    try:
        opts,args = getopt.getopt(argv,"hi:t:p:vd:g:",["interface=","type=","period=","verbose=","diagnostic=","gpio="])
    except getopt.GetoptError:
        sys.stderr.write("COMMAND ERROR")
        print(sys.exc_info())
        exit()
    if opts == []:
        print("default parameters are used: ")
        print("GPIO = "+str(GPIO_PRESENT) +" INTERFACE = "+str(_CHANNEL_))
        print("BUSTYPE = "+str(_BUSTYPE_) +" STDOUT = "+str(verbosity))
        print("DIAGNOSTIC = "+str(diagnostic) +" TIMING = timestamp from logs")
    else:
        for opt,arg in opts:
            if opt == '-h':
                print("USAGE")
                print("-i or --interface, select a can or vcan interface enabled. [DEFAULT: vcan0]")
                print("-t or --type, select the socket type y want to use. [DEFAULT: socketCAN]")
                print("-p or --period, select periodic ms sending time for ALL messages to replay. [DEFAULT: log timestamp]")
                print("-v or --verbose, candump on file, dump example at ./DOC/Jun-19-2020_12-45-32 [DEFAULT: disabled]")
                print("-d or --diagnostic, 1 = enable the bus to send diagnostic request messages. [DEFAULT: disabled]")
                print("-g or --gpio,0 = disable GPIO input [DEFAULT: enabled if hardware present]")
                exit()
            elif opt == '-i' or opt == '--interface':
                _CHANNEL_ = arg
            elif opt == '-t' or opt == '--type':
                _BUSTYPE_=arg
            elif opt == '-p' or opt == '--period':
                timing = float(arg)/1000
                get_timestamp_from_file = False
            elif opt == '-v' or opt == '--verbose':
                verbosity = True
                file_name = datetime.now().strftime("%b-%d-%Y_%H-%M-%S")
                print("verbose=candump, OUT="+file_name)
            elif opt == '-d' or opt == '--diagnostic':
                if arg == '1':
                    diagnostic = True
                    print("diagnostic request enabled")
                else:
                    diagnostic = False
            elif opt == '-g' and GPIO_PRESENT == True:
                if arg == '0':
                    GPIO_PRESENT = False
                    print("GPIO input disabled")
    
    print(_CHANNEL_,_BUSTYPE_,timing)
    _DBC_FILE_ = load_db()
    try:
        bus_wr = can.interface.Bus(channel=str(_CHANNEL_),bustype=str(_BUSTYPE_))
        bus_rd = can.interface.Bus(channel=str(_CHANNEL_),bustype=str(_BUSTYPE_))
    except:
        sys.stderr.write("BUS_INIT_ ERROR")
        print(sys.exc_info())
        exit()
    db=cantools.database.load_file('DBCS/'+str(_DBC_FILE_))
    messages,tot_selectable = map(db) #messages is a dict of messages that y choose to replay,tot_selectable is a dict of all messages available
    if diagnostic == True:
        #add diagnostic messages to dictionaries
        tot_selectable,diagnostic_name_1 = addMessageToDict(messages,tot_selectable,db,diagnostic_id_1)
        tot_selectable,diagnostic_name_2 = addMessageToDict(messages,tot_selectable,db,diagnostic_id_2)
    init_block_events(messages,tot_selectable)
    if GPIO_PRESENT:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(23,GPIO.IN,pull_up_down=GPIO.PUD_DOWN)
            print("waiting for k15..")
            while 1:
                if(GPIO.input(23)==True):
                    print("k15 on.")
                    break
                time.sleep(0.2)
            threading.Thread(target=K15listener).start() #only if k15 is on, k15listener() is started
    try:
        print("LINKS MAP")
        print("___________________________")
        for message in messages.values():
            if (message == diagnostic_name_1) or (message == diagnostic_name_2): #diagnostic use diff thread
                continue
            writer.append(threading.Thread(target=writeOnBus, args=("WRITER_"+str(message),bus_wr.state,bus_wr,message,timing,db,get_timestamp_from_file)))
            writer[threads].start()
            for key,value in messages.items():
                if value == message:
                    print("message: "+str(message)+" linked to index " +str(key))
                    break
            threads += 1
        if diagnostic == True:
            #diagnosticRQ(nome,description,bus,db,frame_id)
            writer.append(threading.Thread(target=diagnosticRQ, args=("WRITER_DIAGNOSTIC_0",bus_wr.state,bus_wr,db,diagnostic_id_1)))
            writer[threads].start()
            threads += 1
            writer.append(threading.Thread(target=diagnosticRQ, args=("WRITER_DIAGNOSTIC_1",bus_wr.state,bus_wr,db,diagnostic_id_2)))
            writer[threads].start()
            threads += 1
            for key,value in messages.items():
                if (value == diagnostic_name_1) or (value == diagnostic_name_2):
                    print("message: "+str(value)+" linked to index " +str(key))
        print("___________________________")
        #thread_event_block(current,all,bus_wr,timing,db,get_timestamp_from_file)
        blocking=threading.Thread(target=thread_event_block,args=(messages,tot_selectable,bus_wr,timing,db,get_timestamp_from_file))
        blocking.start()
        if verbosity == True:
            reader = threading.Thread(target=dump,args=(file_name,bus_rd))
            reader.start()
        for x in range(0,threads): 
            writer[x].join()         
        bus_wr.shutdown()
        blocking.join()
        if verbosity == True:
            reader.join()
            bus_rd.shutdown()
    except:
        sys.stderr.write("ERROR ON _startup_")
        print(sys.exc_info())
        exit()
        
"""
function used to avoid cantools.encode.ErrorValue exception that terminate the transmission
**INFO:
    -if a signal is out of bounds, rewrite a correct value
"""

def check_bounds_routine(dictionary,message_encoded):
    structure = {} #key: signal_name,value = signal structure
    for signal in message_encoded.signals:
        structure[signal.name] = signal
    for signal,value in dictionary.items():
        for sig_name in structure.keys():
            if signal == sig_name:
                maximum = structure.get(sig_name).maximum
                minimum = structure.get(sig_name).minimum
                if maximum!= None and value > maximum:
                    dictionary[signal] = maximum
                elif minimum!= None and value < minimum:
                    dictionary[signal] = minimum
                break
    return dictionary
        
"""
function that replay a .csv log as a CAN message
**PARAMETERS:
    -bus: socket where to send messages
    -message_to_send: CAN message name (.csv file name)
    -timing: user selected period for sending (DEFAULT = timestamp of .csv file)
    -database: dbc
    -default_ts: flag, if 1 than timing is user selected, if 0 than timing is DEFAULT
**INFO:
    -read a csv file which contains signals value for each can message generated
    -this funtion reads each cvs row and decode it to a proper can message before sending in the canbus
    -the decoding is done by message_data_struture.encode() can function that fills message_data_structure from given dictionary
    -the dictionary contains signal name as keys, and respective value as signals value. ex: {'NotFilteredFuelLevel': 500,...} for message STATUS_B_CAN2
"""

def replay(bus,message_to_send,timing,database,default_ts):
    # csv ---> can message
    keepPlay = True
    i=1
    mydictionary = {}
    headers = []
    period = 0
    timex = ""
    timey = ""
    line_count = 0
    if default_ts: 
        with open('LOGS/'+str(message_to_send.name)+".csv") as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                line_count += 1
                if line_count == 2:
                    timex = row
                if line_count == 3:
                    timey = row
                    period = getTimeStamp(timex,timey)
                    break
            csv_file.close()
            #print("timestamp = "+str(period)+" s, message: "+str(message_to_send.name))
            timing = period
    line_count = 0
    tot_played = 0
    while keepPlay:
        with open('LOGS/'+str(message_to_send.name)+".csv") as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                if keep_running[message_to_send.name].isSet():
                    if not stop_bus.isSet(): #k15listener() set this object to True if k15 goes off during execution
                        if line_count == 0:
                            for i in range(len(row)):
                                mydictionary[row[i]] = {}
                                headers.append(row[i])
                            line_count += 1
                        else:
                            for i in range(len(row)):
                                mydictionary[headers[i]] = float(row[i])
                            del mydictionary['timestamp']
                            #here y have the message ready to send
                            try:
                                #check bounds
                                mydictionary = check_bounds_routine(mydictionary,message_to_send)
                                encoded=message_to_send.encode(mydictionary)
                                bus.send(can.Message(arbitration_id=message_to_send.frame_id,data=encoded))
                                time.sleep(timing)
                            except:
                                #terminate job if exception occurs
                                sys.stderr.write("ERROR ON REPLAY")
                                print(sys.exc_info())
                                if not wait_to_stdout.isSet():
                                    wait_to_stdout.set()
                                keepPlay = False
                                break
                            line_count += 1
                            tot_played += 1
                    else:
                        print("k15 signal off, threading.event() detected")
                        print("Processed "+str(tot_played)+" signals for file "+str(message_to_send.name))
                        keepPlay = False
                        break
                else:
                    print("pause event detected")
                    print("Processed "+str(tot_played)+" signals for file "+str(message_to_send.name))
                    wait_to_stdout.set()
                    keep_running[message_to_send.name].wait()
                    print("play event detected, resuming "+str(message_to_send.name))
                    wait_to_stdout.set()
            line_count = 0
    csv_file.close()
        
"""
**INFO:
    -function than retrive real timestamp from .csv file
"""

def getTimeStamp(row_1,row_2):
    timestamp = 0.0
    timestamp = float(row_2[0])-float(row_1[0])
    return float(format(timestamp,'.3f'))
    
"""
********MAIN*******
"""

if __name__ == "__main__":
    try:
        stop_bus.clear()
        _startup_(sys.argv[1:],GPIO_PRESENT)
        #be sure to clean GPIO whenever an exit() is called somewhere
        print("main_app terminated")
    except SystemExit: 
        print(sys.exc_info())
        if GPIO_PRESENT:
            GPIO.cleanup()
        exit()




