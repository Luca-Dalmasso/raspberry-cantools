#!/usr/bin/python

import argparse
import curses
import sys, getopt
import threading
import traceback
import cantools
import can
import re
import os

"""
TERMINAL GUI FOR CAN MESSAGES RECEIVED
"""

#--------------
should_redraw = threading.Event()
stop_bus = threading.Event()
can_messages = {}
can_messages_translated = {}
can_messages_db_names = {}
can_messages_counter = {}
can_messages_lock = threading.Lock()
""" ----------------------------------------"""

""" VERY IMPORTANT MESSAGES ARE BLACKLISTED """

BLACKLIST = ["MOT1","MOT2","MOT3","MOT5","MOTSEL","STATUS_C_ECM","STATUS_C_ECM2","STATUS_C_VCU",
             "STATUS_C_ECM5","STATUS_C_ECM6","STATUS_C_TCM_MTA_DCTM"]

""" ----------------------------------------"""

WHITELIST = {}
#--------------

"""
*read from bus function implemented with a timeout to be non-blocking
*only when gui is closed this ffucntion close the program
*gui closed --> stop_bus event = 1 --> program exit()
"""

def read_bus(bus_device):
    message = None
    message = bus_device.recv(2)
    if message == None:
        if not stop_bus.is_set():
            return None
        else:
            exit()
    return message

"""
*build the traslation of the message by decoding it with the database
"""

def getTranslation(db,msg):
    found = False
    for message in db.messages:
        if msg.arbitration_id==message.frame_id:
            tmp = str(db.decode_message(msg.arbitration_id,msg.data))
            found=True
            break     
    if found==False:
        tmp = "not reconized"
    return tmp

"""
*this function is used as the main  thread
*calls the read_bus fucntion and fill all global dictionaries with messages received and respective datas encoded with getTranslation(-)
*i use the lock() can_messages_lock to avoid raice conditions and illegal access to the global variables by the rest of the program (gui)
*this funtion runs until event stop_bus is set = 1
"""

def bus_run_loop(bus_device,db):
    frame = ["","","",""]
    tmp_str = ""
    msg_index = 0
    while not stop_bus.is_set():
        message = read_bus(bus_device)#message read from bus translated or not
        if message == None:#timeout from read_bus function
            continue
        translation = getTranslation(db,message).split(',')
        frame_id = message.arbitration_id    
        # Add the frame to the can_messages dict and tell the main thread to refresh its content
        with can_messages_lock:
            if len(WHITELIST.keys()) == 0:
                WHITELIST[msg_index] = frame_id
                can_messages_counter[frame_id] = 0
                msg_index += 1
            if len(WHITELIST.keys()) != 0 and frame_id not in WHITELIST.values():
                WHITELIST[msg_index] = frame_id
                can_messages_counter[frame_id] = 0
                msg_index +=1
            can_messages[frame_id] = message
            can_messages_translated[frame_id] = translation
            can_messages_counter[frame_id] += 1
            if len(can_messages_db_names.keys()) == 0 and translation[0] != "not reconized":
                can_messages_db_names[frame_id] = db.get_message_by_frame_id(frame_id).name
            if len(can_messages_db_names.keys()) > 0 and translation[0] != "not reconized" and frame_id not in can_messages_db_names.keys():
                can_messages_db_names[frame_id] = db.get_message_by_frame_id(frame_id).name
            # set this param in order to enable the redraw
            should_redraw.set()
                
"""
*init the main look of the gui and colors
"""

def init_window(stdscr):
    menu = ['MESSAGE READ','TRANSLATION']
    # Don't print typed character
    #curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.clear()
    stdscr.refresh()
    screen_height , screen_width = stdscr.getmaxyx()
    # Set getch() to non-blocking
    stdscr.nodelay(True)
    # turn off cursor blinking
    curses.curs_set(0)
    # color scheme for selected row
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    """ COLOR USED TO DISPLAY CAN MESSAGES NAMES """
    """ COLOR GREEN = MESSAGE ON BLACKLIST """
    """ COLOR YELLOW = MESSAGE NOT IN BLACKLIST """
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW) 
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
    #color used to display errors
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_RED)
    root_window = stdscr.derwin(screen_height, screen_width, 0, 0)
    partition = screen_width // 2
    if partition < 90:
        partition = 90
    c1 = 1
    r1 = 1
    color_print(r1,c1,menu[0],1,root_window)
    color_print(screen_height - 3, 1, "Press 'q' to quit",1,root_window)
    color_print(screen_height - 3, partition, "Press 'q' to quit",1,root_window)
    for entry in range(1,len(menu)):
        c1 = c1 + partition
        color_print(r1,c1,menu[entry],1,root_window)
    color_print(screen_height - 3, c1, "Message displayed: ",1,root_window)
    root_window.refresh() 
    root_window.box()
    return root_window,partition,c1,screen_height,screen_width,r1

def color_print(y, x, text, pair_num,window):
        window.attron(curses.color_pair(pair_num))
        window.addstr(y, x, text)
        window.attroff(curses.color_pair(pair_num))

"""
*main gui function that access global dictionary to fill the terminal screen gui
*it uses lock()
*it makes use of should_redraw event.
*should_redraw event = 1 --> new data available from main thread
"""

def main(stdscr, bus_thread):
    win,partition,c1,screen_height,screen_width,r1 = init_window(stdscr)
    index_to_print = 0
    total = 0
    while True:
        # should_redraw is set by the serial thread when new data is available
        c = stdscr.getch()
        if c == ord('q') or not bus_thread.is_alive():
            stop_bus.set()
            break
        elif c == curses.KEY_RESIZE:
            win,partition,c1,screen_height,screen_width,r1 = init_window(stdscr)
        elif c == curses.KEY_UP:
            index_to_print += 1
            win,partition,c1,screen_height,screen_width,r1 = init_window(stdscr)
        elif c == curses.KEY_DOWN:
            index_to_print -= 1
            win,partition,c1,screen_height,screen_width,r1 = init_window(stdscr)
        if should_redraw.is_set():
            #fill rows and refresh
            #Make sure we don't read the can_messages dict while it's being written to in the serial thread
            with can_messages_lock:
                row = r1 + 4  # The first column starts a bit lower to make space for the 'press q to quit message'
                c1 = 1
                total = len(WHITELIST.keys())
                if index_to_print >= total:
                    index_to_print = 0
                elif index_to_print < 0:
                    index_to_print = 0
                msg = str(can_messages.get(WHITELIST.get(index_to_print)))
    
                if len(can_messages_db_names.keys()) > 0:
                    if WHITELIST.get(index_to_print) in can_messages_db_names.keys():
                        name_readable = can_messages_db_names.get((WHITELIST.get(index_to_print)))
                        if name_readable in BLACKLIST:
                            color_print(r1, c1+20, name_readable,3,win)
                        else:
                            color_print(r1, c1+20, name_readable,2,win)
                msg  = re.sub(r"\s+", ' ', msg)
                msg_tr = can_messages_translated.get(WHITELIST[index_to_print])
                win.addstr(row, c1, str(msg))
                win.addstr(row + 2,c1,"Count: "+str(can_messages_counter.get(WHITELIST[index_to_print])))
                win.addstr(row + 4,c1,"Byte transmitted: "+str((can_messages.get(WHITELIST.get(index_to_print)).dlc)*can_messages_counter.get(WHITELIST[index_to_print])))
                for string in msg_tr:
                    if (row + 1) >= (screen_height - 3):
                        #control used to avoid crash for addrow() error!, if this line is printed on terminal, increase the screen's height
                        color_print(row, c1 + partition,"H",4,win)
                        break
                    if (len(string) + c1 + partition) > (screen_width):
                        #control used to avoid crash for addrow() error!, if this line is printed on terminal, increase the screen's width
                        color_print(row, c1 + partition,"W",4,win)
                        row = row + 1
                        continue
                    win.addstr(row,c1 + partition,str(string))
                    row = row + 1
                row = row + 1
                color_print(screen_height - 3, c1 + partition + 20, str(index_to_print + 1)+"/"+str(total),1,win)
                win.refresh()
                should_redraw.clear()
                
"""
*this function allow y to select one database if exists in "DBCS" directory
*all dbcs must be placed in DBCS directory, if no .dbc are found, the fuction searcher() exits
"""

def load_db():
    dbcs,dim = searcher('DBCS','.dbc')
    print("you can select one dbs, please select by index")
    for i in range(dim):
        print(str(i)+" "+str(dbcs[i]))
    try:
        l = int(input("> "));
    except:
        sys.stderr.write("ERROR ON DB_LOAD")
        print(sys.exc_info())
        exit()
    if (l >= dim) or (l<0) :
        print("input not correct!")
        exit()
    return dbcs[l]

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


if __name__ == '__main__':
    bus_thread = None
    _CHANNEL_ = 'vcan0'
    _BUSTYPE_ = 'socketcan'
    try:
        opts,args = getopt.getopt(sys.argv[1:],"hi:t:",["interface=","type="])
    except getopt.GetoptError:
        sys.stderr.write("args not reconized, type 'python out.py -h' for help")
        exit()
    if opts == []:
        print("default parameters will be used")
    else:
        for opt,arg in opts:
            if opt == '-h':
                print("-i or --interface= 'canx,vcany,ecc..', -t or --type= 'socketcan,..'")
                exit()
            elif opt == '-i' or opt == '--interface':
                _CHANNEL_ = arg
            elif opt == '-t' or opt == '--type':
                _BUSTYPE_ = arg
    try:
        bus = can.interface.Bus(channel=_CHANNEL_, bustype=_BUSTYPE_)
        db = load_db()
        db = cantools.database.load_file('DBCS/'+str(db))
        # Start the bus reading background thread
        bus_thread = threading.Thread(target=bus_run_loop, args=(bus,db))
        bus_thread.start()
        # Make sure to draw the UI the first time even if there is no data
        should_redraw.clear()
        # Start the main loop
        curses.wrapper(main, bus_thread)
    except:
        sys.stderr.write("ERROR ON __MAIN__")
        print(sys.exc_info())
    finally:
        # Cleanly stop bus thread before exiting
        if bus_thread:
            stop_bus.set()
            bus_thread.join()
        bus.shutdown()



