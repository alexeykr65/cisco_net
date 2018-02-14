#!/usr/bin/env python
#
#

import netmiko
import argparse
import os
import re
import time
import multiprocessing
from datetime import datetime
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException

fileName = ""
flagDebug = 1
flagPrint = False
flagSave = False
flagLoad = False
listDevices = dict()
listParamNetmiko = ['device_type', 'ip', 'username', 'password', 'port', 'verbose', 'secret']
commandDefault = "sh version"

description = "Cisco_Net: Configure cisco devices and get information from it, v1.0"
epilog = "http://ciscoblog.ru\nhttps://github.com/alexeykr65"


def GetDate():
    '''
    This function returns a tuple of the year, month and day.
    '''
    # Get Date
    now = datetime.now()
    day = str(now.day)
    month = str(now.month)
    year = str(now.year)
    hour = str(now.hour)
    minute = str(now.minute)

    if len(day) == 1:
        day = '0' + day
    if len(month) == 1:
        month = '0' + month

    return year, month, day, hour, minute


def CmdArgsParser():
    global flagDebug, fileName, commandDefault, flagPrint, flagSave, flagLoad
    if flagDebug > 0: print "Analyze options ... "
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument('-f', '--file', help='File name with cisco devices', dest="fileName", default='cisco_devices.conf')
    parser.add_argument('-d', '--debug', help='Debug information view(default =1, 2- more verbose)', dest="flagDebug", default=1)
    parser.add_argument('-c', '--command', help='Get command from routers', dest="command", default="")
    parser.add_argument('-p', '--printdisplay', help='View on screen', action="store_true")
    parser.add_argument('-s', '--savetofile', help='Save to Files', action="store_true")
    parser.add_argument('-l', '--loadfiles', help='Load from Files', action="store_true")

    arg = parser.parse_args()

    flagDebug = int(arg.flagDebug)
    fileName = arg.fileName
    if flagDebug > 0: print "File config: " + fileName
    if arg.command:
        commandDefault = arg.command
    if arg.printdisplay:
        flagPrint = True
    if arg.savetofile:
        flagSave = True
    if arg.loadfiles:
        flagLoad = True


def FileConfigAnalyze():
    global listDevices
    if flagDebug > 0: print "Analyze source file : " + fileName + " ..."
    if not os.path.isfile(fileName):
        if flagDebug > 0: print "Configuration File : " + fileName + " does not exist"
        return
    f = open(fileName, 'r')
    countDevices = 0
    for sLine in f:
        if re.match("^\s*$", sLine) or re.match("^#.*", sLine):
            continue
        for sParam in sLine.split(';'):
            tmpParam, tmpValue = sParam.strip().split('=')
            if flagDebug > 1: print "Parmater: " + tmpParam + "Value: " + tmpValue
            if countDevices in listDevices:
                listDevices[countDevices][tmpParam] = tmpValue
            else:
                listDevices[countDevices] = dict({tmpParam: tmpValue})
        countDevices += 1
    f.close()
    if flagDebug > 1: print listDevices


def getStructureNetmiko(infoDevice):
    resNetmiko = dict()
    for tParam in listParamNetmiko:
        if tParam in infoDevice:
            resNetmiko[tParam] = infoDevice[tParam]
    return resNetmiko


def ConnectToRouter(infoDevice, runCommand, mp_queue):
    return_data = dict()
    proc = os.getpid()
    netmikoInfo = getStructureNetmiko(infoDevice)
    try:
        SSH = netmiko.ConnectHandler(**netmikoInfo)
        SSH.read_channel()
        find_hostname = SSH.find_prompt()
        hostname = re.match("^([^#>]*)[#>]", find_hostname).group(1).strip()
        print "Process pid: " + str(proc) + ' Hostname: {0}'.format(hostname) + ' IpDevice: {ip}'.format(**infoDevice)
        if flagLoad:
            # print "Name File: " + infoDevice['conf_file']
            commandReturn = SSH.send_config_from_file(infoDevice['conf_file'])
        else:
            commandReturn = SSH.send_command(runCommand)
    except (NetMikoTimeoutException, NetMikoAuthenticationException) as e:
        print "Cannot connect to ip : " + 'IpDevice: {ip}'.format(**infoDevice)
        print "Error: " + str(e)
        return None
    return_data[hostname] = commandReturn
    mp_queue.put(return_data)
    SSH.disconnect()


def main():
    CmdArgsParser()
    FileConfigAnalyze()
    mp_queue = multiprocessing.Queue()
    processes = []

    print "\nStart time: " + str(datetime.now())
    for numDevice in listDevices:
        p = multiprocessing.Process(target=ConnectToRouter, args=(listDevices[numDevice], commandDefault, mp_queue))
        processes.append(p)
        p.start()
    results = []
    while any(p.is_alive() for p in processes):
        time.sleep(0.1)
        while not mp_queue.empty():
            results.append(mp_queue.get())

    for p in processes:
        p.join()
    for listRes in sorted(results):
        for res in listRes:
            if flagPrint:
                print ("=" * 100)
                print "Router : " + res
                print listRes[res]
            if flagSave:
                year, month, day, hour, minute = GetDate()
                # Create Filename
                filebits = [res, "config", day, month, year, hour, minute + ".txt"]
                fileSave = '-'.join(filebits)
                f = open(fileSave, 'w')
                f.write(listRes[res])
                f.close()
    print "\nEnd time: " + str(datetime.now())


if __name__ == '__main__':

    main()
