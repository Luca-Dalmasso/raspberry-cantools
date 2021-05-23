#!/bin/bash

function checkif(){
	if [[ ! -d /sys/class/net/${1} ]]; then
		printf 'no such interface, must be created\n' 
		return 0
	else
		if [ $(cat "/sys/class/net/${1}/operstate") = "down" ]; then
			printf 'iface down, must be upped\n'
			return 1
		fi
	fi
	exit 0
}


if [ $# = 1 ]; then
	checkif $1
	if [ $? = "0" ]; then
		printf 'creating interface %s\n' "$1"
		sudo ip link add dev ${1} type can bitrate 500000
		sudo ifconfig ${1} up
	else
		printf 'bringing up interface %s\n' "$1"
		sudo ifconfig ${1} up 
	fi
fi
exit 0
