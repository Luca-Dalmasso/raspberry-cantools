#!/usr/bin/python3

import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import asksaveasfilename as ask_save
import os
import sys
import can
import cantools

#parameters to choose at runtime:
fields = ('Iface', 'Socket type', 'Period', 'Diagnostic enable',
          'GPIO enable', 'Dump enable','C-Can LOG','P-Can LOG')
#paramteres indexes
IF_FIELD = 'Iface'
SOCK_FIELD = 'Socket type'
TIME_FIELD = 'Period'
DIAG_ENABLE_FIELD = 'Diagnostic enable'
GPIO_ENABLE_FIELD = 'GPIO enable'
DUMP_ENABLE_FIELD = 'Dump enable'

"""
*ARP_DEFINE_CAN_INDEX=280 is a value that can be read in file /sys/class/net/<iface>/type (ARP PROTOCOL CONSTANT)
*280 means that the device is a Controller Area Network interface
*more information about kernel_global_definition can be found in ./DOC/others/RFC_826_ARP_GLOBAL.html
 which is copy of a .h file used by every linux kernel ARP protocol (THE REAL .h IS LOCATED SOMEWHERE IN THE KERNEL, DO NOT EDIT IT)
"""
ARP_DEFINE_CAN_INDEX = 280
"""
*this directory contains symbolic links to all /dev network interfaces loaded in the system.
 the command 'ip link show' uses this directory to show interfaces configuration
*more information can be found in the document ./DOC/others/kernel_sys_class_net.pdf
"""
INTERFACES_PATH = '/sys/class/net/'
USAGE_PATH = 'TOOL_USAGE.txt'
LOG_DIR = 'EDITED'

#GUI initialization of labels and textEntry
def makeform(root, fields,c_values,p_values):
    entries = {}
    for field in fields:
        row = tk.Frame(root)
        lab = tk.Label(row, width=22, text=field+": ", anchor='w')
        ent = tk.Entry(row,highlightbackground="black",
                relief=tk.RAISED)
        ent.insert(0, "0")
        row.pack(side=tk.TOP, 
                 fill=tk.X, 
                 padx=5, 
                 pady=5)
        lab.pack(side=tk.LEFT)
        if field == 'C-Can LOG':
            n = tk.StringVar()
            c_can_msgs = ttk.Combobox(row, width = 22, textvariable = n) 
            # Adding combobox drop down list 
            c_can_msgs['values'] = c_values
            c_can_msgs.pack(side=tk.RIGHT,expand=tk.YES,
                 fill=tk.X)
        elif field == 'P-Can LOG':
            n = tk.StringVar()
            p_can_msgs = ttk.Combobox(row, width = 22, textvariable = n) 
            # Adding combobox drop down list 
            p_can_msgs['values'] = p_values
            p_can_msgs.pack(side=tk.RIGHT,expand=tk.YES,
                 fill=tk.X)
        else:
            ent.pack(side=tk.RIGHT, 
                 expand=tk.NO,
                 fill=tk.X)
        entries[field] = ent
    return entries,c_can_msgs,p_can_msgs

"""
*check interface status and configuration by reading OPERSTATE,
 CARRIER,PHYDEV,PHYDEVTYPE files in INTERFACES_PATH directory
*writes diagnostic in the textbox
*Y CAN USE iface SELECTED ONLY IF THIS FUCTION RETURNS True,
 False means that something is wrong with  the selected interface
"""

def ifup(if_path,T,iface):
    OPERSTATE = str(if_path) + "/operstate"
    CARRIER = str(if_path) + "/carrier"
    PHYDEV = str(if_path) + "/phydev"
    PHYDEVTYPE = str(if_path) + "/type"
    usable = False
    try:
        if os.path.exists(OPERSTATE):
            with open(OPERSTATE, "r") as opstate:
                T.insert(tk.END,"operstate "+str(iface)+'\n')
                for row in opstate:
                    if row == "up":
                        T.insert(tk.END,"Operstate: UP\n")
                        usable = True
                        break
                    elif row == "down":
                        T.insert(tk.END,"Operstate: DOWN\n")
                        usable = False
                        break
                    else:
                        T.insert(tk.END,"Operstate: UNKNOWN\n")
                        break
                opstate.close()
        if os.path.exists(CARRIER):
            with open(CARRIER, "r") as carrier:
                T.insert(tk.END,"carrier "+str(iface)+'\n')
                for row in carrier:
                    if row == "1\n":
                        T.insert(tk.END,"physical link is UP and ready\n")
                        usable = True
                        break
                    else:
                        T.insert(tk.END,"physical link is DOWN!\n")
                        usable = False
                        break
                carrier.close()
        if os.path.exists(PHYDEV):
            with open(PHYDEV, "r") as dev:
                T.insert(tk.END,"device symbolic link reference for "+str(iface)+" ")
                for row in dev:
                    T.insert(tk.INSERT,str(row)+'\n')
                dev.close()
        if os.path.exists(PHYDEVTYPE):
            with open(PHYDEVTYPE, "r") as devtype:
                T.insert(tk.END,"device tipe "+str(iface)+'\n')
                for row in devtype:
                    typ = int(row)
                    if typ == ARP_DEFINE_CAN_INDEX:
                        T.insert(tk.END,"THIS IS RECONIZED AS CAN DEVICE\n")
                        usable = True
                        break
                    else:
                        T.insert(tk.END,"NOPE! THIS IS NOT A Controller Area Network interface..\n")
                        usable = False
                        break
                devtype.close()
        return usable
    except:
        sys.stderr.write("ERROR ON CHECK\n")
        print(sys.exc_info())
        return False

"""
CALLBACK FOR Check Button
*wrapper for ifup() function
"""

def check(entries,T):
    iface = str(entries[IF_FIELD].get())
    T.delete('1.0',tk.END)
    T.insert(tk.INSERT,"DIAGNOSTIC REPORT:\n")
    T.insert(tk.END,"iface: "+str(iface)+'\n')
    path = str(INTERFACES_PATH)+str(iface)
    try:
        flag_exists = os.path.exists(path)
        if flag_exists:
            T.insert(tk.END,str(iface)+": exists\n")
            if not ifup(path,T,iface):
                return False
            else:
                T.insert(tk.END,str(iface)+": UP AND READY TO BE USED\n")
                return True
        else:
            T.insert(tk.END,str(iface)+": not such interface\n")
    except:
        sys.stderr.write("ERROR ON CHECK\n")
        print(sys.exc_info())

"""
CALLBACK FOR BUTTON 'Launch'
*if checks are all ok, this funcion Launch 'main_app.py' or 'out.py' with all args selected
*this fucntion is loaded when button 'Launch' or 'Monitor' are clicked
"""

def launcher(entries,T,app):
    ARGS_MONITOR = ['xterm','-geometry','180x50','-hold','-e','./out.py']
    ARGS_MAIN = ['xterm','-geometry','100x50','-hold','-e','./main_app.py']
    iface = str(entries[IF_FIELD].get())
    socktype = str(entries[SOCK_FIELD].get())
    period = str(entries[TIME_FIELD].get())
    diag_enable = str(entries[DIAG_ENABLE_FIELD].get())
    dump_enable = str(entries[DUMP_ENABLE_FIELD].get())
    gpio_enable = str(entries[GPIO_ENABLE_FIELD].get())
    if period != "0":
        ARGS_MAIN.append("-p"+period)
    if socktype != "0":
        ARGS_MAIN.append("-t"+socktype)
        ARGS_MONITOR.append("-t"+socktype)
    if diag_enable == "1":
        ARGS_MAIN.append("-d"+diag_enable)
    if dump_enable == "1":
        ARGS_MAIN.append("-v")
    if gpio_enable == "1":
        ARGS_MAIN.append("-g"+gpio_enable)
    elif gpio_enable == "0":
        ARGS_MAIN.append("-g"+gpio_enable)
    if check(entries,T):
        ARGS_MAIN.append("-i"+iface)
        ARGS_MONITOR.append("-i"+iface)
        T.delete('1.0',tk.END)
        T.insert(tk.INSERT,"DIAGNOSTIC OK\n")
        if app == "MAIN":
            T.insert(tk.END,"MAIN APP on xterm\n")
            command_launcher(ARGS_MAIN)
        elif app == "MONITOR":
            T.insert(tk.END,"MONITOR APP on xterm\n")
            command_launcher(ARGS_MONITOR)
    else:
        T.delete('1.0',tk.END)
        T.insert(tk.INSERT,"DIAGNOSTIC NOT OK\n")
        T.insert(tk.END,"SELECTED INTERFACE NOT\n")
        T.insert(tk.END,"USE CHECK BUTTON FOR MORE DIAGNOSTIC DETAILS\n")

#fork for command       
def command_launcher(args):
    pid = os.fork()
    if pid == 0:
        #CHILD
        os.execv('/usr/bin/xterm',args)
    #PARENT

"""
this fucntion is called by '?' icon in the Menu.
used for showing a message in the textBox that helps to understand tool usage
The message printed is read from the file './TOOL_USAGE.txt'
"""

def help(T):
    T.delete('1.0',tk.END)
    if os.path.exists(USAGE_PATH):
        with open(USAGE_PATH, "r") as file:
            for row in file:
                T.insert(tk.END,str(row))
        file.close()

"""
CALLBACK FOR BUTTON Iface UP
this function makes use of './_can_.sh', './_vcan_.sh' shell scripts,
can create and bring up a canX or vcanX interface that you wrote in Iface label
"""

def ifaceUP(entries,T):
    ARGS = ['xterm','-geometry','100x50','-hold','-e']
    T.delete('1.0',tk.END)
    iface = str(entries[IF_FIELD].get())
    T.insert(tk.INSERT,"Trying to set up "+str(iface)+'\n')
    T.insert(tk.END,"This makes use of scripts that must be executed with root privileges\n")
    T.insert(tk.END,"For istance a password may be asked\n")
    if iface.find("vcan") == 0:
        T.insert(tk.END,"Reconized a pattern for a virtual device\n")
        ARGS.append("./_vcan_.sh "+iface)
        command_launcher(ARGS)
    elif iface.find("can") == 0:
        T.insert(tk.END,"Reconized a pattern for a can device\n")
        ARGS.append("./_can_.sh "+iface)
        command_launcher(ARGS)
    else:
        T.insert(tk.END,"No pattern reconized..\n")
        T.insert(tk.END,"Try with vcan(x) for a virtual can\n")
        T.insert(tk.END,"or with can(x) for can\n")
        T.insert(tk.END,"x can be an integer any other letter\n")
        
"""
creates an empty(just with can signals headers) .csv log
"""
        
def save(filepath,fields):
    n = len(fields)-1
    filepath = LOG_DIR+'/'+filepath+'.csv'
    with open(filepath,"w") as out:
        out.write("timestamp,")
        for i in range(0,n):
            out.write(str(fields[i])+',')
        out.write(str(fields[n]))       
    out.close()
    T.insert(tk.INSERT,"Created file: "+str(filepath)+'\n')

"""
CALLBACK FOR BUTTONS "C-CAN LOG" and "P-CAN LOG"
print some info about can message selected from comboboxes
calls 'save()' fucntion with can message name and signals as args
"""

def create(message,T):
    T.delete('1.0',tk.END)
    signals = []
    T.insert(tk.INSERT,"Signals info for can message: "+str(message.name)+'\n')
    for signal in message.signals:
        try:
            signals.append(signal.name)
            T.insert(tk.END,"----------------------------")
            T.insert(tk.END,'\n')
            T.insert(tk.END,signal.name)
            T.insert(tk.END,'\n')
            T.insert(tk.END,signal.comment)
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Signed: "+str(signal.is_signed))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Float: "+str(signal.is_float))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Decimal: "+str(signal.is_float))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Minumum: "+str(signal.minimum))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Maximum: "+str(signal.maximum))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Length: "+str(signal.length))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Unit: "+str(signal.unit))
            T.insert(tk.END,'\n')
            T.insert(tk.END,"Scale: "+str(signal.scale))
            T.insert(tk.END,'\n')
            T.insert(tk.END,signal.choices)
            T.insert(tk.END,'\n')
            T.insert(tk.END,"----------------------------")
            T.insert(tk.END,'\n')
        except:
            continue
    save(message.name,signals) 
        
    

"""
MAIN ROUTINE FOR THE GUI EVENTS
"""

if __name__ == '__main__':
    dbc_can_c=cantools.database.load_file('DBCS/P250FL14_C-CAN_R1_23072019_E4A_13412.dbc')
    dbc_can_p=cantools.database.load_file('DBCS/FCA_IET_database_v1.0.28.dbc')
    c_values = []
    p_values = []
    for message in dbc_can_c.messages:
        c_values.append(message.name)
    for message in dbc_can_p.messages:
        p_values.append(message.name)
    root = tk.Tk()
    root.title("Raspberry CAN Tool")
    root.resizable(False,False)
    ents,c_can_msgs,p_can_msgs = makeform(root, fields,c_values,p_values)
    S = tk.Scrollbar(root)
    T = tk.Text(root, height=17,width=50,highlightbackground="black",
                highlightthickness=2)
    S.pack(side=tk.RIGHT)
    T.pack(side=tk.LEFT)
    S.config(command=T.yview)
    T.config(yscrollcommand=S.set)
    menubar = tk.Menu()
    menuhelp = tk.Menu(menubar,tearoff = 0)
    menuhelp.add_command(label='Help',
           command=(lambda: help(T)))
    menubar.add_cascade(label='?',menu=menuhelp)
    root.config(menu=menubar)
    quote = "Info dialog\n"
    T.insert(tk.END, quote)
    
    b1 = tk.Button(root, text='Check',
           command=(lambda: check(ents,T)))
    b1.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b1.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    b2 = tk.Button(root, text='Launch',
           command=(lambda: launcher(ents,T,"MAIN")))
    b2.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b2.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    b3 = tk.Button(root, text='Monitor',
           command=(lambda: launcher(ents,T,"MONITOR")))
    b3.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b3.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    b4 = tk.Button(root, text='Quit', command=root.quit)
    b4.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b4.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    b5 = tk.Button(root, text='Iface UP',
           command=(lambda: ifaceUP(ents,T)))
    b5.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b5.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    b6 = tk.Button(root, text='C-CAN LOG',
           command=(lambda: create(dbc_can_c.get_message_by_name(c_values[c_can_msgs.current()]),T)))
    b6.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b6.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    b7 = tk.Button(root, text='P-CAN LOG',
           command=(lambda: create(dbc_can_p.get_message_by_name(p_values[p_can_msgs.current()]),T)))
    b7.config(highlightbackground="black",relief=tk.RAISED,width = 10)
    b7.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    root.mainloop()
