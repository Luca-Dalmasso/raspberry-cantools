# Rasberry tool for CAN debug automotive


[ALL DOCUMENTATION](DOC) 
<br>

[HOW TO SETUP RASPBERRY AS CAN SNIFFER](DOC/rasp-setup)  very important steps in order to configure your rasberry to be a can device.
In partucular the rasberry needs to be configured to  be able to detect a PEAK-USB device and mount it as interface during boot process.
<br>


There are 3 main scrips:
- [main_app.py](main_app.py): this scripts basically replicate on a can bus (virtual or physical), that can be accessed by a socket, some [can messages](LOGS) formatted as .csv files.

		USAGE: python main_app.py -h

- [out.py](out.py): terminal GUI, it reads and translate all traffic in a selected can-bus (physical or virtual) 

		USAGE; python out.py -h (./out.py -h)

- [raspyTOOL.py](raspyTOOL.py): (only with python3): general gui used to use all others scripts that otherwise need to be configured and started manually. <br> A more accurate usage document is [here](TOOL_USAGE.txt)

All .dbc files inside the DBCS directory are private due to possible copyright issues. <br>
A .dbc file is a database that contains information used by a can device in order to translate can messages into a human-readable format.
	 
