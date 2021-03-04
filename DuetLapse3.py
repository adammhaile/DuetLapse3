#!python3

"""
#Python program to take Time Lapse photographs during a print on 
#   a Duet based 3D printer and convert them into a video. 
#
# From the original work of Danal Estes
# Copyright (C) 2020 Danal Estes all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#Extended by Stuart Strolin
# Copyright (C) 2020 Stuart Strolin all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#
# Developed on Raspberry Pi and WSL with Debian Buster and on Windows 10. SHOULD work on most other linux didtributions. 
# For USB or Pi camera, The Camera MUST be physically attached to the Pi computer.  
# For Webcam, the camera must be network reachable and via a defined URL for a still image.
# For Stream   the camera must be network reachable and via a defined URL
# The Duet printer must be RepRap firmware V3 and must be network reachable. 
# 
#
"""
global duetLapse3Version
duetLapse3Version = '3.4.0'
import subprocess
import sys
import platform
import argparse
import time
import requests
import json
import os
import socket
import threading
import psutil


def setStartValues():
    global zo1, zo2, printState, capturing, duetStatus, timePriorPhoto1, timePriorPhoto2, frame1, frame2
    zo1 = 0                         # Starting layer for Camera1
    zo2 = 0                         # Starting layer for Camera2
    printState = 'Not Capturing'
    capturing = False
    duetStatus = 'Not yet determined'
    
    #initialize timers
    timePriorPhoto1 = time.time()
    timePriorPhoto2 = time.time()
    
    #reset the frame counters
    frame1 = 0       
    frame2 = 0
    
    
###########################
# Methods begin here
###########################

def whitelist(parser):
    #Environment
    parser.add_argument('-duet',type=str,nargs=1,default=['localhost'],help='Name of duet or ip address. Default = localhost')
    parser.add_argument('-poll',type=float,nargs=1,default=[5])
    parser.add_argument('-basedir',type=str,nargs=1,default=[''],help='default = This program directory')
    parser.add_argument('-instances',type=str,nargs=1,choices=['single','oneip','many'],default=['single'],help='Default = single')
    parser.add_argument('-logtype',type=str,nargs=1,choices=['console','file','both'],default=['both'],help='Default = both')
    parser.add_argument('-verbose',action='store_true',help='Output stdout and stderr from system calls')
    parser.add_argument('-host',type=str,nargs=1,default=['0.0.0.0'],help='The ip address this service listens on. Default = 0.0.0.0')
    parser.add_argument('-port',type=int,nargs=1,default=[0],help='Specify the port on which the server listens. Default = 0')
    parser.add_argument('-keeplogs',action='store_true', help='Does not delete logs.')    
    parser.add_argument('-novideo',action='store_true', help='Does not create a video.')    
    parser.add_argument('-deletepics',action='store_true', help='Deletes images on Terminate')    
    
    #Execution
    parser.add_argument('-dontwait',action='store_true',help='Capture images immediately.')
    parser.add_argument('-seconds',type=float,nargs=1,default=[0])
    parser.add_argument('-detect',type=str,nargs=1,choices= ['layer', 'pause', 'none'],default=['layer'],help='Trigger for capturing images. Default = layer')
    parser.add_argument('-pause',type=str,nargs=1,choices= ['yes', 'no'],default=['no'],help='Park head before image capture.  Default = no')
    parser.add_argument('-movehead',type=float,nargs=2,default=[0.0,0.0], help='Where to park head on pause, Default = 0,0')
    parser.add_argument('-standby',action='store_true',help='Wait for command from http listener')
    #Camera
    parser.add_argument('-camera1',type=str,nargs=1,choices=['usb','pi','web','stream','other'],default=['usb'],help='Mandatory Camera. Default = usb')
    parser.add_argument('-weburl1',type=str,nargs=1,default=[''],help='Url for Camera1 if web or stream') 
    parser.add_argument('-camera2',type=str,nargs=1,choices=['usb','pi','web','stream','other'],default=[''],help='Optional second camera. No Default')
    parser.add_argument('-weburl2',type=str,nargs=1,default=[''],help='Url for Camera2 if web or stream')
    #Video
    parser.add_argument('-extratime',type=float,nargs=1,default=[0],help='Time to repeat last image, Default = 0')
    #Overrides
    parser.add_argument('-camparam1',type=str,nargs=1,default=[''],help='Camera1 Capture overrides. Use -camparam1="parameters"')
    parser.add_argument('-camparam2',type=str,nargs='*',default=[''],help='Camera2 Capture overrides. Use -camparam2="parameters"')
    parser.add_argument('-vidparam1',type=str,nargs=1,default=[''],help='Camera1 Video overrides. Use -vidparam1="parameters"')    
    parser.add_argument('-vidparam2',type=str,nargs=1,default=[''],help='Camera2 Video overrides. Use -vidparam2="parameters"')
    return parser



def init():

    parser = argparse.ArgumentParser(description='Create time lapse video for Duet3D based printer. V'+duetLapse3Version, allow_abbrev=False)
    parser = whitelist(parser)
    args=vars(parser.parse_args())

    #Environment
    global duet, basedir, poll, instances, logtype, verbose, host, port
    global keeplogs, novideo, deletepics
    #Derived  globals
    global duetname, debug, ffmpegquiet, httpListener   
    duet     = args['duet'][0]
    basedir  = args['basedir'] [0]
    poll  = args['poll'][0]
    instances = args['instances'] [0]
    logtype   = args['logtype'] [0]    
    verbose = args['verbose']
    host = args['host'][0]
    port = args['port'][0]
    keeplogs = args['keeplogs']    
    novideo = args['novideo']
    deletepics = args['deletepics']    
    #Execution
    global dontwait, seconds, detect, pause, movehead, standby       
    dontwait = args['dontwait']
    seconds  = args['seconds'][0]
    detect   = args['detect'][0]
    pause    = args['pause'][0]
    movehead = args['movehead']  
    standby = args['standby']
    #Camera
    global camera1, camera2, weburl1, weburl2     
    camera1   = args['camera1'][0]
    camera2   = args['camera2'][0]
    weburl1   = args['weburl1'][0]
    weburl2   = args['weburl2'][0]


    #Video
    global extratime   
    extratime = str(args['extratime'] [0])
    
    #Overrides
    global camparam1, camparam2, vidparam1, vidparam2
    camparam1   = args['camparam1'][0]
    camparam2   = args['camparam2'][0]
    vidparam1   = args['vidparam1'][0]    
    vidparam2   = args['vidparam2'][0] 
    
    ############################################################
    #Check to see if this instance is allowed to run  
    ############################################################
    
    #  What OS are we using?
    global win
    operatingsystem = platform.system()
    if(operatingsystem == 'Windows'):
        win = True
    else:
        win = False
        
    thisinstance = os.path.basename(__file__)
    if not win:
        thisinstance = './'+thisinstance
    proccount = checkInstances(thisinstance, instances)
               
    ####################################################
    # Setup for logging and filenames
    ####################################################
    
    #pid is used to create unique filenames
    global pid       
    pid = str(os.getpid())
     
    # How much output
    if (verbose) :
        debug = ''
        ffmpegquiet = ''
    else:
        ffmpegquiet = ' -loglevel quiet'
        if (not win):
            debug = ' > /dev/null 2>&1'
        else:
            debug = ' > nul 2>&1'
            
    #duetname used for filenames and directories
    duetname = duet.replace('.' , '-')        
            
    # set directories for files
    global topdir, baseworkingdir, workingdir, logname
 
    if (basedir == ''): basedir = os.path.dirname(os.path.realpath(__file__))

    if (win):
        topdir = basedir+'\\'+socket.getfqdn()+'\\'+duetname
        baseworkingdir = topdir+'\\'+pid #may be changed later
        logname = pid+'_'+time.strftime('%y-%m-%dT%H:%M:%S',time.localtime())+'.log'
        logfilename = logname.replace(':',u'\u02f8') # cannot use regular colon in windows file names
        logname = topdir+'\\'+logname
        logfilename = topdir+'\\'+logfilename
        subprocess.call('mkdir "'+topdir+'"'+debug, shell=True)
    else:
        topdir = basedir+'/'+socket.getfqdn()+'/'+duetname
        baseworkingdir = topdir+'/'+pid  #may be changed later
        logname = pid+'_'+time.strftime('%y-%m-%dT%H:%M:%S',time.localtime())+'.log'
        logfilename = logname.replace(':',u'\u02f8') # cannot use regular colon in windows file names
        logname = topdir+'/'+logname
        logfilename = topdir+'/'+logfilename
        subprocess.call('mkdir -p "'+topdir+'"'+debug, shell=True)
        
    #  Clean up files
    cleanupFiles('startup')    
    
    # Create a custom logger
    import logging
    global logger
    logger = logging.getLogger('DuetLapse3')
    logger.setLevel(logging.DEBUG)

# Create handlers and formats
    if ('console' in logtype or 'both' in logtype) : 
        c_handler = logging.StreamHandler()
        c_format = logging.Formatter(duet+' %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)
   
    if ('file' in logtype or 'both' in logtype) :
        f_handler = logging.FileHandler(logfilename, mode='w')    
        f_format = logging.Formatter(duet+' - %(asctime)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)


    
    ####################################################
    # Display options selected.
    ####################################################
    logger.info('')
    logger.info("################### Options selected for this run #####################")
    logger.info("#Environment Settings:")
    logger.info("# printer         = {0:50s}".format(duet))
    logger.info("# basedir         = {0:50s}".format(basedir))
    logger.info("# poll            = {0:50s}".format(str(poll))) 
    logger.info("# logtype         = {0:50s}".format(logtype)) 
    logger.info("# verbose         = {0:50s}".format(str(verbose)))
    logger.info("# os              = {0:50s}".format(operatingsystem))
    logger.info("# host            = {0:50s}".format(str(host)))    
    logger.info("# port            = {0:50s}".format(str(port)))
    logger.info("# pid             = {0:50s}".format(pid))
    logger.info("# keeplogs        = {0:50s}".format(str(keeplogs)))    
    logger.info("# novideo         = {0:50s}".format(str(novideo)))    
    logger.info("# deletepics      = {0:50s}".format(str(deletepics)))    
    logger.info("#Execution Setings:")    
    logger.info("# dontwait        = {0:50s}".format(str(dontwait)))
    logger.info("# seconds         = {0:50s}".format(str(seconds)))   
    logger.info("# detect          = {0:50s}".format(detect))
    logger.info("# pause           = {0:50s}".format(pause))
    if (movehead[0] != 0 and movehead[1] != 0):
        logger.info("# movehead    = {0:6.2f} {1:6.2f} ".format(movehead[0],movehead[1]))
    logger.info("# standby         = {0:50s}".format(str(standby)))
    logger.info("#Camera1 Settings:")
    logger.info("# camera1         = {0:50s}".format(camera1))
    logger.info("# weburl1         = {0:50s}".format(weburl1))
    if (camparam1 != ''):
        logger.info("# Camera1 Override:")    
        logger.info("# camparam1       = {0:50s}".format(camparam1))
    if (camera2 != ''):
        logger.info("# Camera2 Settings:")
        logger.info("# camera2     =     {0:50s}".format(camera2))
        logger.info("# weburl2     =     {0:50s}".format(weburl2))
    if (camparam2 != ''):
        logger.info("# Camera2 Override:")
        logger.info("# camparam2    =    {0:50s}".format(camparam2))   
    logger.info("# Video Settings:")
    logger.info("# extratime   =     {0:50s}".format(extratime))
    if (vidparam1 != ''):
        logger.info("# Video1 Override:")
        logger.info("# vidparam1    =    {0:50s}".format(vidparam1))
    if (vidparam2 != ''):
        logger.info("# Video2 Override:")
        logger.info("# vidparam2    =    {0:50s}".format(vidparam2))
    logger.info("###################################################################")
    logger.info('')
           
 
    
    ###############################################
    #derived parameters
    ##############################################
                         
    #Polling interval should be at least = seconds so as not to miss interval
    if (poll > seconds and seconds != 0): poll = seconds    #Need to poll at least as often as seconds
    #if ('none' in detect and seconds != 0): poll = seconds  #No point in polling more often
        
    #  Port number must be given for httpListener to be active
    if (port != 0):
        httpListener = True
              
    ########################################################################       
    # Inform regarding valid and invalid combinations
    #########################################################################
    
    
    #Invalid Combinations that will abort program     
    
    if (camera1 !='other' and camparam1 !=''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera1+' cannot be used with camparam1')  
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if (camera2 !='other' and camparam2 !=''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera2+' cannot be used with camparam2')  
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if ((camera1 =='usb' or camera1 == 'pi')  and win):   #  These do not work on WIN OS
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera1+' cannot be on Windows OS')  
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if ((camera2 =='usb' or camera2 == 'pi')  and win):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera2+' cannot be on Windows OS')  
        logger.info('************************************************************************************')
        sys.exit(2)

    if ((seconds <= 0) and ('none' in detect)):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination:: -seconds '+str(seconds)+' and -detect '+detect+' nothing will be captured.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if ((not movehead == [0.0,0.0]) and ((not 'yes' in pause) and (not 'pause' in detect))):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-movehead {0:1.2f} {1:1.2f}" requires either "-pause yes" or "-detect pause".'.format(movehead[0],movehead[1]))
        logger.info('************************************************************************************')
        sys.exit(2)

    if (('yes' in pause) and ('pause' in detect)):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-pause yes" causes this program to pause printer when')
        logger.info('other events are detected, and "-detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************')
        sys.exit(2)
        
    #Information and Warnings
        
    if (standby and not httpListener):
        logger.info('************************************************************************************')
        logger.info('Warning: -standby ignored.  It has no effect unless http Listener is active.')
        logger.info('Specify -localhost and -port to activate http Listener')
        logger.info('************************************************************************************')        
        
    if ((seconds > 0) and (not 'none' in detect)):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds '+str(seconds)+' and -detect '+detect+' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')
        
    if (startNow() and not dontwait):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds '+str(seconds)+' and -detect '+detect)
        logger.info('This combination implies -dontwait and will be set automatically')
        logger.info('************************************************************************************')
        dontwait = True
        
    if ('pause' in detect):
        logger.info('************************************************************************************')
        logger.info('* Note "-detect pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this program will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "-movehead nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this program force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "-pause yes -detect layer" or "-pause yes -seconds nnn".')
        logger.info('************************************************************************************')


    if ('yes' in pause):
        logger.info('************************************************************************************')
        logger.info('* Note "-pause yes" means this program will pause the printer when the -detect and / or ')
        logger.info('* -seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this program detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "-detect pause"')
        logger.info('************************************************************************************')
        
    logger.info('')
    if (novideo and deletepics):
        logger.info('************************************************************************************')
        logger.info('Warning: The combination of -novideo and -deletepics will not create any output')  
        logger.info('************************************************************************************')         
    
        
        

    def checkDependencies(camera):        
        #
        if (not win):
           finder = 'whereis'
        else:
            finder = 'where'
            
        if ('usb' in camera):
            if (20 > len(subprocess.check_output(finder+' fswebcam', shell=True))):
                logger.info("Module 'fswebcam' is required. ")
                logger.info("Obtain via 'sudo apt install fswebcam'")
                sys.exit(2)

        if ('pi' in camera):
            if (20 > len(subprocess.check_output(finder+' raspistill', shell=True))):
                logger.info("Module 'raspistill' is required. ")
                logger.info("Obtain via 'sudo apt install raspistill'")
                sys.exit(2)

        if ('stream' in camera):
            if (20 > len(subprocess.check_output(finder+' ffmpeg', shell=True))):
                logger.info("Module 'ffmpeg' is required. ")
                logger.info("Obtain via 'sudo apt install ffmpeg'")
                sys.exit(2)

        if ('web' in camera):
            if (20 > len(subprocess.check_output(finder+' wget', shell=True))):
                logger.info("Module 'wget' is required. ")
                logger.info("Obtain via 'sudo apt install wget'")
                sys.exit(2)
        
        if (20 > len(subprocess.check_output(finder+' ffmpeg', shell=True))):
            logger.info("Module 'ffmpeg' is required. ")
            logger.info("Obtain via 'sudo apt install ffmpeg'")

            sys.exit(2)

    checkDependencies(camera1)
    if (camera2 != ''): checkDependencies(camera2)

    
    # Get connected to the printer.
    
    global apiModel

    # Get connected to the printer.

    apiModel, printerVersion = getDuetVersion()
    
    if (apiModel == 'none'):
        logger.info('')
        logger.info('###############################################################')
        logger.info('The printer at '+duet+' did not respond')
        logger.info('Check the ip address or logical printer name is correct')
        logger.info('Duet software must support rr_model or /machine/status')
        logger.info('###############################################################')
        logger.info('')
        sys.exit(2)
    
    majorVersion = int(printerVersion[0])

    if (majorVersion >= 3):
        logger.info('')
        logger.info('###############################################################')
        logger.info('Connected to printer at '+duet+' using Duet version '+printerVersion+' and API access using '+apiModel)
        logger.info('###############################################################')
        logger.info('')
    else:
        logger.info('')
        logger.info('###############################################################')
        logger.info('The printer at '+duet+' needs to be at version 3 or above')
        logger.info('The version on this printer is '+printerVersion)
        logger.info('###############################################################')
        logger.info('')
        sys.exit(2)
    
    #Allows process running in background or foreground to be gracefully
    # shutdown with SIGINT (kill -2 <pid>
    import signal

    def quit_gracefully(*args):
        logger.info('!!!!!! Stopped by SIGINT or CTL+C - Post Processing !!!!!!')
        nextAction('terminate')
        #threading.Thread(target=nextAction, args=('terminate',)).start()

    if __name__ == "__main__":
        signal.signal(signal.SIGINT, quit_gracefully)


"""
End of init()
"""

#####################################################
##  Utility Functions
#####################################################
"""
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
"""

def getRunningInstancePids():
    pidlist = []
    for p in psutil.process_iter():
        if (('python3' in p.name() or 'pythonw' in p.name()) and '-duet' in p.cmdline()): #Check all other python3 instances
            pidlist.append(str(p.pid))  
    return pidlist

def getPidDirs():
    dirlist = []
    for item in os.listdir(topdir):
        if os.path.isdir(os.path.join(topdir, item)):
            dirlist.append(item)    
    return dirlist
    
def createWorkingDir(baseworkingdir):
    global workingdir_exists, workingdir
    jobname = getDuetJobname(apiModel)
    if jobname != '':
        jobname = jobname.replace(' ','_')
        jobname = jobname.replace('.gcode','')
        jobname = jobname.replace('gcodes/','')
        jobname = jobname.replace(':',u'\u02f8')
        split_jobname = jobname.split("/", 1)
        jobname = split_jobname[1]
        workingdir = baseworkingdir+'_'+jobname
    else:
        workingdir = baseworkingdir
        
    if win:
        subprocess.call('mkdir "'+workingdir+'"'+debug, shell=True)
    else:
        subprocess.call('mkdir -p "'+workingdir+'"'+debug, shell=True)
    logger.info('Working directory created at: '+workingdir)    
    workingdir_exists = True
    return workingdir
    
def cleanupFiles(phase):
    global workingdir_exists
    print('Cleaning up phase:  '+phase)
    pidlist = []
    dirlist = []
    pidlist = getRunningInstancePids()
    dirlist = getPidDirs()

    # Make and clean up directorys.
    #Make sure there is a directory for the resulting video
    
    if (phase == 'startup'):
        if win:
            for dirs in dirlist:
                split_dirs = dirs.split("-", 1)
                dirpid = split_dirs[0]
                if dirpid not in pidlist:
                    subprocess.call('rmdir "'+topdir+'\\'+dirs+'" /s /q'+debug, shell=True)
            if (not keeplogs and len(pidlist) == 1):  #only delete logs if no other processes running
                print('Deleting log files')
                subprocess.call('del /s "'+topdir+'\\"*.log'+debug, shell=True)   #Note position of last " so that shell expands *.log portion 
        else:
            for dirs in dirlist:
                split_dirs = dirs.split("-", 1)
                dirpid = split_dirs[0]
                if dirpid not in pidlist:
                    subprocess.call('rm -rf "'+topdir+'/'+dirs+'"'+debug, shell=True)           
            if (not keeplogs and len(pidlist) == 1):  #only delete logs if no other processes running
                subprocess.call('rm -f "'+topdir+'/"*.log'+debug, shell=True)   #Note position of last " so that shell expands *.log portion
    
    elif (phase == 'standby'):  #delete images directory will be recreated on first capture
        if workingdir_exists:    
            if win:
                subprocess.call('rmdir "'+workingdir+'" /s /q'+debug, shell=True)          
            else:
                subprocess.call('rm -rf "'+workingdir+'"'+debug, shell=True)
        workingdir_exists = False
    
    elif (phase == 'restart'):
        workingdir_exists = False
    
    elif (phase == 'terminate'):
        if deletepics:
            if win:
                subprocess.call('rmdir "'+workingdir+'" /s /q'+debug, shell=True)           
            else:
                subprocess.call('rm -rf "'+workingdir+'"'+debug, shell=True)
            
        
def startNow():
    global action
    if (standby and httpListener) :
        action = 'standby'
        return False
    elif (seconds > 0 and (dontwait or 'none' in detect)):
        action = 'start'
        return True
    else:
        action = 'start'
        return False
        
def getThisInstance(thisinstancepid):
    thisrunning = 'Could not find a process running with pid = '+str(thisinstancepid)
    for p in psutil.process_iter():
        if (('python3' in p.name() or 'pythonw' in p.name()) and thisinstancepid == p.pid):
            cmdline = str(p.cmdline())
            #clean up the appearance
#            cmdline = cmdline.replace('python3','')
#            cmdline = cmdline.replace('pythonw','')
            cmdline = cmdline.replace('[','')
            cmdline = cmdline.replace(']','')
            cmdline = cmdline.replace(',','')
            cmdline = cmdline.replace("'",'')
            cmdline = cmdline.replace('  ','')
            pid = str(p.pid)
            thisrunning = 'This program is running with<br>Process id:    '+pid+'<br>Command line:    '+cmdline+''
           
    return  thisrunning        
    
#####################################################
##  Processing Functions
#####################################################

def checkInstances(thisinstance, instances):
    proccount = 0
    allowed = 0
       
    for p in psutil.process_iter():

         if (('python3' in p.name() or 'pythonw' in p.name()) and thisinstance in p.cmdline()):
            proccount += 1
            if ('single' in instances):
                allowed += 1
            if ('oneip' in instances):
                if duet in p.cmdline():
                    allowed += 1
    
    if (allowed > 1):
           print('')
           print('#############################')
           print('Process is already running... shutting down.')
           print('#############################')
           print('')
           sys.exit(0)

    return proccount

def checkForPause(layer):
    # Checks to see if we should pause and reposition heads.
    #Dont pause until printing has actually started and the first layer is done
    #This solves potential issues with the placement of pause commands in the print stream
    #Before / After layer change
    if (layer < 2 and not dontwait): return 
    
    if (pause == 'yes'):  #DuetLapse is controlling when to pause        
        logger.info('Requesting pause via M25')
        sendDuetGcode(apiModel, 'M25')    # Ask for a pause
        loop = 0
        while (1):
            time.sleep(1)  # wait a second and try again
            if(getDuetStatus(apiModel) == 'paused'):
                break
            else:
                loop += 1               
            if (loop == 10):   #limit the counter in case there is a problem
                logger.info('Loop exceeded: Target was: paused')
                break
          
#    if (alreadyPaused or duetStatus == 'paused'):
    if (duetStatus == 'paused'):
        if(not movehead == [0.0,0.0]):   #optional repositioning of head
            logger.info('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(movehead[0],movehead[1]))
            sendDuetGcode(apiModel, 'G0 X{0:4.2f} Y{1:4.2f}'.format(movehead[0],movehead[1]))
            loop = 0
            while (1):
                time.sleep(1)  # wait a second and try again
                xpos, ypos, _ = getDuetPosition(apiModel)
                if ((abs(xpos - movehead[0]) < .2) and (abs(ypos - movehead[1]) < .2)):   #close enough for government work
                    break
                else:
                    loop += 1                    
                if (loop == 10):    #limit the counter in case there is a problem
                    logger.info('Loop exceeded for X,Y: '+str(xpos)+','+str(ypos)+' Target was: '+str(movehead[0])+','+str(movehead[1]))
                    break   
    return

def unPause():
    if (getDuetStatus(apiModel) == 'paused'):
        logger.info('Requesting un pause via M24')
        sendDuetGcode(apiModel, 'M24')    # Ask for an un pause
        loop = 0
        while (1):
            time.sleep(1)  # wait a second and try again
            if(getDuetStatus(apiModel) in ['idle','processing'] ):
                break
            else:
                loop += 1                
            if (loop == 10):    #limit the counter in case there is a problem
                logger.info('Loop exceeded: Target was: un pause')
                break 
    return


def onePhoto(cameraname, camera, weburl, camparam): 
    global frame1, frame2, workingdir
    if not workingdir_exists:
        workingdir = createWorkingDir(baseworkingdir) #created as late as possible - adds job fileName if available
    
    if (cameraname == 'Camera1'):
        frame1 += 1
        frame = frame1
    else:
        frame2 += 1
        frame = frame2
        
    s=str(frame).zfill(8)
    if (win):
        fn = ' "'+workingdir+'\\'+cameraname+'_'+s+'.jpeg"'
    else:
        fn = ' "'+workingdir+'/'+cameraname+'_'+s+'.jpeg"'

    if ('usb' in camera): 
        cmd = 'fswebcam --quiet --no-banner '+fn+debug
            
    if ('pi' in camera): 
        cmd = 'raspistill -t 1 -ex sports -mm matrix -n -o '+fn+debug
            
    if ('stream' in camera):
        cmd = 'ffmpeg'+ffmpegquiet+' -y -i '+weburl+ ' -vframes 1 ' +fn+debug
        
    if ('web' in camera): 
        cmd = 'wget --auth-no-challenge -nv -O '+fn+' "'+weburl+'" '+debug
        
    if ('other' in camera):
        cmd = eval(camparam)
     
    subprocess.call(cmd, shell=True)
    global timePriorPhoto1, timePriorPhoto2
    if (cameraname == 'Camera1'):
        timePriorPhoto1 = time.time()
    else:
        timePriorPhoto2 = time.time()
    
def oneInterval(cameraname, camera, weburl, camparam):
    global frame1, frame2
    global timePriorPhoto1, timePriorPhoto2
    
    #select the prior frame counter
    if (cameraname =='Camera1'):
        frame = frame1
    else:
        frame = frame2
        

    global zo1, zo2
    zn = getDuetLayer(apiModel)
    if ('layer' in detect):
        if ((not zn == zo1 and cameraname == 'Camera1') or (not zn == zo2 and cameraname == 'Camera2')):
            # Layer changed, take a picture.
            checkForPause(zn)
            logger.info(cameraname+': capturing frame '+str(frame)+' at layer '+str(zn)+' after layer change')           
            onePhoto(cameraname, camera, weburl, camparam)            

    elif ('pause' in detect and duetStatus == 'paused'):
            checkForPause(zn)
            logger.info(cameraname+': capturing frame '+str(frame)+' at layer '+str(zn)+' at pause in print gcode')
            onePhoto(cameraname, camera, weburl, camparam)
    
    #update the layer counter        
    if (cameraname == 'Camera1'):
        zo1 = zn
    else:
        zo2 = zn  
                
    #Note that onePhoto() updates timePriorPhoto1 and timePriorPhoto2
    if (cameraname == 'Camera1'):
        elap = (time.time() - timePriorPhoto1)
    else:
        elap = (time.time() - timePriorPhoto2)

    if ((seconds > 0 and seconds < elap) and (dontwait or zn >= 1)):
        checkForPause(zn)
        logger.info(cameraname+': capturing frame '+str(frame)+' at layer '+str(zn)+' after '+str(seconds)+' seconds')
        onePhoto(cameraname, camera, weburl, camparam)
    
def postProcess(cameraname, camera, vidparam):
    
    logger.info('')
    if (cameraname == 'Camera1'):
        frame = frame1
    else:
        frame = frame2
        
    if (frame < 10):
        logger.info(cameraname+': Cannot create video with only '+str(frame)+' frames')
        return
     
    logger.info(cameraname+': now making '+str(frame)+' frames into a video')
    if (250 < frame): logger.info("This can take a while...")
    timestamp = time.strftime('%a-%H-%M',time.localtime())
    
    if (win):
        fn = ' "'+topdir+'\\'+pid+'_'+cameraname+'_'+timestamp+'.mp4"'
    else:
        fn = ' "'+topdir+'/'+pid+'_'+cameraname+'_'+timestamp+'.mp4"'
        
    if (vidparam == ''):
        if (float(extratime) > 0):  #needs ffmpeg > 4.2
            if(win):
                #Windows version does not like fps=10 argument   
                cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+workingdir+'\\'+cameraname+'_%08d.jpeg" -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+' '+fn+debug
            else:
                cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+workingdir+'/'+cameraname+'_%08d.jpeg" -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug
        else: #Using an earlier version of ffmpeg that does not support tpad (and hence extratime)
            if (win):
                cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+workingdir+'\\'+cameraname+'_%08d.jpeg" -vcodec libx264 -y '+fn+debug
            else:
                cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+workingdir+'/'+cameraname+'_%08d.jpeg" -vcodec libx264 -y '+fn+debug
    else:
        cmd = eval(vidparam)              
    subprocess.call(cmd, shell=True)
    logger.info('Video processing complete for '+cameraname)
    logger.info('Video is in file '+fn)
    
#############################################################################
##############  Duet API access Functions
#############################################################################

def urlCall(url,timelimit):
    loop = 0
    limit = 2  #Started at 2 - seems good enough to catch transients
    while (loop < limit):    
        try:
            r = requests.get(url, timeout=timelimit)
            break
        except requests.ConnectionError as e:
            logger.info('')
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('There was a network failure: '+str(e))
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('')            
            loop += 1
            error = 'Connection Error'
        except requests.exceptions.Timeout as e:
            logger.info('')
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')            
            logger.info('There was a timeout failure: '+str(e))
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('')            
            loop += 1
            error = 'Timed Out'
        time.sleep(1)
        
    if (loop >= limit): #Create dummy response
       class r:
           ok = False
           status_code = 9999
           reason = error
       
    return r


def  getDuetVersion():
#Used to get the status information from Duet
    try:
        model = 'rr_model'
        URL=('http://'+duet+'/rr_model?key=boards')
        r = urlCall(URL, 5)
        j = json.loads(r.text)
        version = j['result'][0]['firmwareVersion']
        return 'rr_model', version;
    except:
        try:
            model='/machine/system'
            URL=('http://'+duet+'/machine/status')
            r = urlCall(URL, 5)
            j = json.loads(r.text)
            version = j['boards'][0]['firmwareVersion']
            return 'SBC', version;
        except:
            return 'none', '0';
            
def  getDuetJobname(model):
#Used to get the print jobname from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=job.file.fileName')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                jobname = j['result']
                if jobname is None: jobname = ''
                return jobname           
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status/')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                jobname = j['job']['file']['fileName']
                if jobname is None: jobname = ''
                return jobname
            except requests.exceptions.RequestException as e:
                pass
    logger.info('getDuetJobname failed to get data. Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    return ''            
      

def  getDuetStatus(model):
#Used to get the status information from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=state.status')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                status = j['result']
                return status           
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status/')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                status = j['state']['status']
                return status
            except requests.exceptions.RequestException as e:
                pass
    logger.info('getDuetStatus failed to get data. Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    return 'disconnected'


def  getDuetLayer(model):
#Used to get the status information from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=job.layer')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                layer = j['result']
                if layer is None: layer = 0
                return layer           
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status/')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                layer = j['job']['layer']
                if layer is None: layer = 0
                return layer
            except:
                pass
    logger.info('getDuetLayer failed to get data. Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    return 'disconnected'
        
def  getDuetPosition(model):
#Used to get the current head position from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=move.axes')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                Xpos = j['result'][0]['machinePosition']
                Ypos = j['result'][1]['machinePosition']
                Zpos = j['result'][2]['machinePosition']
                return Xpos, Ypos, Zpos;
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status')
        r = urlCall(URL, 5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                Xpos = j['move']['axes'][0]['machinePosition']
                Ypos = j['move']['axes'][1]['machinePosition']
                Zpos = j['move']['axes'][2]['machinePosition']
                return Xpos, Ypos, Zpos;
            except:
                pass
                
    logger.info('getDuetPosition failed.  Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    logger.info('Returning coordinates as -1, -1, -1')
    return -1, -1, -1;
                
def  sendDuetGcode(model, command):     
#Used to get the status information from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_gcode?gcode='+command)
        r = urlCall(URL, 5)
    else:
        URL=('http://'+duet+'/machine/code')
        r = urlCall(URL, 5)

    if (r.ok):
       return
        
    logger.info('sendDuetGCode failed with code: '+str(r.status_code)+'and reason: '+str(r.reason))
    return

def makeVideo():
    postProcess('Camera1', camera1, vidparam1)
    if (camera2 != ''): postProcess('Camera2', camera2, vidparam2)
    
def terminate():
    global httpListener, listener
    cleanupFiles('terminate')
    #close the nextaction thead if necessary.  nextAction will have close the capturethread
    try: 
        nextactionthread.join(10)
    except:
        pass
    #close the httpthread if necessary
    try:
        httpthread.join(10)
    except:
        pass
    logger.info('Program Terminated')
    os.kill(int(pid),9)


###########################
# Integral Web Server
###########################

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

class MyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory= topdir, **kwargs)    
    
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
    def _refresh(self, message):
        content = f'<html><head><meta http-equiv="refresh" content="60"> </head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!  

    def _html(self, message):
        content = f"<html><head></head><body><h2>{message}</h2></body></html>"
        return content.encode("utf8")  # NOTE: must return a bytes object!
        
    def update_content(self):
        options = 'status, start, terminate'
        global pidlist
        pidlist = []
        localtime = time.strftime('%A - %H:%M',time.localtime())
        #portlist = []
        #runninginstances, pidlist = getRunningInstances(thisinstance, referer)
        thisrunninginstance = getThisInstance(int(pid))
        if (str(zo1) == '-1'):
           thislayer = 'None'
        else:
           thislayer = str(zo1)
           
        if workingdir_exists:
            imagelocation =  'Images are located here: '+workingdir+'<br>'
        else:
            imagelocation = ''
    
        header =    ('DuetLapse3 Version '+duetLapse3Version+'<br>'
                    '<h4>'
                    +thisrunninginstance+'<br><br>'
                    'Logs and Videos are located here: '+topdir+'<br>'
                    +imagelocation+
                    'The logfile for this instance is: '+logname+
                    '</h4>'   
                    )    
        
        status =    ('<h3>'
                    'Status of printer on '+duet+'<br><br>'
                    'Last Updated:  '+localtime+'<br><br>'
                    '<h3>'
                    '<pre>'
                    'Capture Status:            =    '+printState+'<br>'
                    'DuetLapse3 State:          =    '+action+'<br>'
                    'Duet Status:               =    '+duetStatus+'<br>'
                    'Images Captured:           =    '+str(frame1)+'<br>'
                    'Current Layer:             =    '+thislayer+
                    '</pre>'
                    '</h3>'
                    )                                    
        
        buttons =   ('<div class="divider">'
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="status" />'
                    '<input type="submit" value="Status" style="background-color:green"/>'                    
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                    
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="start" />'                                    
                    '<input type="submit" value="Start" style="background-color:orange"/>'
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                    
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="standby" />'                                    
                    '<input type="submit" value="Standby" style="background-color:orange"/>'
                    '</form>'
                    '</div>'                    
                    '<div class="divider">'                                   
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="pause" />'                                   
                    '<input type="submit" value="Pause" style="background-color:pink"/>'
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                   
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="continue" />'                                   
                    '<input type="submit" value="Continue" style="background-color:pink"/>'
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                   
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="snapshot" />'                                   
                    '<input type="submit" value="Snapshot" style="background-color:green"/>'
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                   
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="restart" />'                                   
                    '<input type="submit" value="Restart" style="background-color:yellow"/>'
                    '</form>'
                    '</div>'                    
                    '<div class="divider">'                                     
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="terminate" />'
                    '<input type="submit" value="Terminate" style="background-color:red"/>'
                    '</form>'
                    '</div>'
                    '<div class="divider">'
                    '<form target="_blank" action="http://'+referer+'">'
                    '<input type="hidden" name="files" value= '+topdir+' />'
                    '<input type="submit" value="Files" style="background-color:green"/>'                    
                    '</form>'
                    '</div>'                    
                    '<style type="text/css">'
                    '{'
                    'position:relative;'
                    'width:200px;'
                    '}'
                    '.divider{'
                    'width:200px;'
                    'height:auto;'
                    'display:inline-block;'
                    '}'
                    '.pad30{'
                    'margin-left: 30px;' 
                    '}'
                    'input[type=submit] {'
                    'width: 10em;  height: 2em;'
                    '}'
                    '</style>'
                    )        
        return header , status , buttons;
    
    def do_GET(self):
        if ('favicon.ico' in self.path):
            return
            
        query_components = parse_qs(urlparse(self.path).query)

        if ((query_components and not query_components.get('command')) or (not query_components and self.path != '/')):
            super().do_GET()        
            return    
            
        global referer, refererip
        referer = self.headers['Host']
        split_referer = referer.split(":", 1)
        refererip = split_referer[0]            
        #Update main content
        header, status, buttons = self.update_content()                      
        self._set_headers()       

        global action, options
        options = ['status', 'start', 'standby', 'pause', 'continue', 'snapshot', 'restart', 'terminate']
                                      
        command = ''
        if(query_components.get('command')):
            command = query_components['command'][0]         
            logger.info('!!!!! http '+command+' request received !!!!!')
            
            #check for a valid request
            if (command not in options):
                illegal =   ('<h3>'
                             '<pre>'
                             'Illegal value for ?command=<br>'
                             'Valid options are:   '+''.join(str(e+'   ') for e in options)+
                             '</pre>'
                             '</h3>'
                             )
                
                self.wfile.write(self._html(header+status+buttons+illegal))
                return             

           #process the request
       
            if (command == 'status'):
                refreshing = ('<h3><pre>'
                              'Status will update every 60 seconds'
                              '</pre></h3>'
                              )
                self.wfile.write(self._refresh(header+status+buttons+refreshing))                     
              
            #start / standby
            elif (command == 'start'):
                if (action == 'standby'):
                    available = [e for e in options if e not in command]
                    start =    ('<h3><pre>'
                                'Starting DuetLapse3.<br><br>'
                                'Press Status to refresh'
                                '</pre></h3>'
                                )

                    self.wfile.write(self._html(header+status+buttons+start))                                                
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()
                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))
            
            elif (command == 'standby'):  #can be called at any time
                unwanted = {'pause', 'standby','restart', 'terminate'}
                allowed = [e for e in options if e not in unwanted]
                if (action in allowed):
                    standby =  ('<h3><pre>'
                                'Putting DuetLapse3 in standby mode<br><br>'
                                'Will NOT create a video.<br>'
                                'All captured images will be deleted<br>'
                                'This is the same as if DuetLapse was just started with -standby<br><br>'
                                'Next available action is start'
                                '</pre></h3>'
                                )
                    self.wfile.write(self._html(header+status+buttons+standby))
                    #Fire and forget - assumed to be successful
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()

                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))

            #pause / continue
            elif (command == 'pause'):
                unwanted = {'pause', 'standby', 'continue', 'restart', 'terminate'}
                allowed = [e for e in options if e not in unwanted]
                if (action in allowed):
                    pause =    ('<h3><pre>'
                                'Pausing DuetLapse3.<br><br>'
                                'Next available action is continue'
                                '</pre></h3>'
                                )
                    self.wfile.write(self._html(header+status+buttons+pause))                                
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()
                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))
            
            elif (command == 'continue'):
                if (action == 'pause'):
                    available = [e for e in options if e not in command]                    
                    unpause = ('<h3><pre>'
                               'Continuing DuetLapse3<br><br>'
                               'Press Status to refresh'
                               '</pre></h3>'
                               )
                    self.wfile.write(self._html(header+status+buttons+unpause))
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()
                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))
            
            # snapshot / restart / terminate
                    
            elif (command == 'snapshot'):
                unwanted = {'snapshot', 'restart', 'terminate'}
                allowed = [e for e in options if e not in unwanted]
                if (action in allowed):
                    snapshot =  ('<h3><pre>'
                                 'Creating an interim snapshot video<br><br>'
                                 'Will first create a video with the current images then continue<br><br>'
                                 'Press Status to refresh'
                                 '</pre></h3>'
                                 )
                    self.wfile.write(self._html(header+status+buttons+snapshot))                                                
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()
                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))                   
                                      
            elif (command == 'restart'):
                unwanted = {'snapshot','restart', 'terminate'}
                allowed = [e for e in options if e not in unwanted]
                if (action in allowed):
                    restart =  ('<h3><pre>'
                                'Restarting DuetLapse3<br><br>'
                                'Will first create a video with the current images<br>'
                                'Then delete all captured images<br>'
                                'The restart behavior is the same as initially used to start DuetLapse3<br><br>'
                                'Press Status to refresh'
                                '</pre></h3>'
                                )
                    self.wfile.write(self._html(header+status+buttons+restart))                                                
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()
                                                
                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))
                                                
            elif (command == 'terminate'):
                unwanted = {'snapshot','restart', 'terminate'}
                allowed = [e for e in options if e not in unwanted]                
                if (action in allowed):
                    terminate = ('<h1><pre>'
                                 'Terminating DuetLapse3<br><br>'
                                 'Will finish last image capture, create a video, then terminate.'
                                 '</pre></h1>'
                                 )            
                    self.wfile.write(self._html(header+status+buttons+terminate))                            
                    logger.info('!!!!! Sending http Terminate request !!!!!')
                    #nextAction(command)
                    threading.Thread(target=nextAction, args=(command,)).start()

                else:
                    self.wfile.write(self._html(header+status+buttons+self.ignoreCommandMsg(command,action)))

            return
        else:    
            refreshing = ('<h3><pre>'
                          'Status will update every 60 seconds'
                          '</pre></h3>'
                          )
            self.wfile.write(self._refresh(header+status+buttons+refreshing))        
          
            return
    """
    End of do_Get
    """
    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass
            
    def ignoreCommandMsg(self,command,action):
        msg = ('<h3>'
               '<pre>'
               +command+
               ' request has been ignored<br>'
               +action+
               ' state is currently enabled'
               '</h3>'
               )
        return msg
            
def createHttpListener():    
    global listener
    listener = ThreadingHTTPServer((host, port), MyHandler)
    listener.serve_forever()
    sys.exit(0)  #May not be needed since never returns from serve_forever
    
    
###################################
#  Main Control Functions
###################################

def captureLoop():  #Run as a thread
    global capturing, printState, duetStatus
    capturing = True 
    disconnected = 0
    printState = 'Not Capturing'
    lastDuetStatus = ''

    while(capturing):  #action can be changed by httpListener or SIGINT or CTL+C

        duetStatus=getDuetStatus(apiModel)

        if(duetStatus == 'disconnected'): #provide some resiliency for temporary disconnects
            disconnected += 1
            logger.info('Printer is disconnected - Trying to reconnect')
            if (disconnected > 10): #keep trying for a while just in case it was a transient issue
                logger.info('')
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')                
                logger.info('Printer was disconnected from Duet for too long')
                logger.info('Finishing this capture attempt')
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info('')                
                printState = 'Disconnected'
                nextactionthread = threading.Thread(target=nextAction, args=('terminate',))   #Note comma in args is needed
                nextactionthread.start()
                return
                
        if (duetStatus != lastDuetStatus): # What to do next? 
            logger.info('****** Duet status changed to: '+duetStatus+' *****')
            # logical states for printer are printing, completed
            if (duetStatus == 'idle' and printState == 'Capturing'):  #print job has finished
                printState = 'Completed'
                logger.info('****** Print State changed to '+printState+' *****')            
            elif (duetStatus in ['processing','idle'] or (duetStatus == 'paused' and detect == 'pause')):
                printState = 'Capturing'
                logger.info('****** Print State changed to: '+printState+' *****')
            else:
                printState = 'Waiting'
                logger.info('****** Print State changed to: '+printState+' *****')          


        if (printState == 'Capturing'):
            oneInterval('Camera1', camera1, weburl1, camparam1)
            if (camera2 != ''): oneInterval('Camera2', camera2, weburl2, camparam2)
            unPause()  #Nothing should be paused at this point
            disconnected = 0
        elif (printState == 'Completed'):
            logger.info('Print Job Completed')
            printState = 'Not Capturing'
            nextactionthread = threading.Thread(target=nextAction, args=('completed',))  #Note comma in args is needed
            nextactionthread.start()
            return
            
        if (capturing): #If no longer capturing - sleep is by-passed for speedier exit response  
            lastDuetStatus = duetStatus
            time.sleep(poll)  # poll every n seconds - placed here to speeed startup           
            
    logger.info('Exiting Capture loop')
    capturing = False
    printState = 'Not Capturing'
    return    #The return ends the thread

def nextAction(nextaction):  #can be run as a thread
    global action, capturethread, capturing
    global options
    action = nextaction          #default
    #All nextactions assume the capturethread is shutdown
    try:
        capturing= False        #Signals captureThread to shutdown
        time.sleep(1)           #Wait a second to avoid race condition e.g. printer paused to capture image
        capturethread.join(10)  #Timeout is to wait up to 10 seconds for capture thread to stop
    except:
        pass
         
    # This test is positionally sensitive
    if (nextaction == 'completed'):    #end of a print job
        if (httpListener):            #controlled by http listener
            nextaction = 'restart'
        else:                         #running as a one-off
            nextaction = 'terminate'

    logger.info('++++++ Entering '+action+' state ++++++')

    if (nextaction == 'start'):
        capturing = True 
    elif (nextaction == 'standby'):
        cleanupFiles(nextaction)   #clean up and start again
        setStartValues()
    if (nextaction == 'pause'):
        pass 
    elif (nextaction == 'continue'):
        capturing = True
    elif (nextaction == 'snapshot'):
        makeVideo()
        capturing = True
    elif (nextaction == 'restart'):
        makeVideo()
        cleanupFiles(nextaction)   #clean up and start again
        setStartValues()
        startNow()
        if (action == 'start'): capturing = True  #what we do here is the same as the original start action 
    elif(nextaction == 'terminate'):
        if novideo:
            logger.info('Video creation was skipped')
        else:
            makeVideo()
        terminate()
    elif (nextaction == 'disconnected'):
        terminate()
    
    if (capturing):
        action = 'start'
        logger.info('++++++ Entering '+action+' state ++++++')
        capturethread = threading.Thread(target=captureLoop, args=())
        capturethread.start()
        
    return
    
def startMessages():
    if (startNow()):
        logger.info('')
        logger.info('##########################################################')
        logger.info('Will start capturing images immediately')
        logger.info('##########################################################')
        logger.info('')
    else:
        logger.info('')
        logger.info('##########################################################')
        if('layer' in detect):
            logger.info('Will start capturing images on first layer change')
        elif('pause' in detect):
            logger.info('Will start capturing images on first pause in print stream')
        logger.info('##########################################################')
        logger.info('')

    if (standby):
        logger.info('')
        logger.info('##########################################################')
        logger.info('Will not start until command=start received from http listener')
        logger.info('##########################################################')
        logger.info('')

    logger.info('')
    logger.info('##########################################################')
    logger.info('Video will be created when printing ends.')
    logger.info('On Linux   -  press Ctrl+C one time to stop capture and create video.')
    logger.info('On Windows -  Ctrl+C will NOT create a video. You must use the http listener')
    logger.info('##########################################################')
    logger.info('')

    return

def startHttpListener(host,port):
    sock = socket.socket()
    if (host == '0.0.0.0' and win):  #Windows does not report properly with 0.0.0.0
        portcheck = sock.connect_ex(('127.0.0.1', port))
    else:
        portcheck = sock.connect_ex((host, port))

    if (portcheck == 0):
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        logger.info('Sorry, port '+str(port)+' is already in use.')
        logger.info('Shutting down this instance.')
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        sys.exit(2)
    
    #import threading
    httpthread = threading.Thread(target=createHttpListener, args=()).start()
    #httpthread.start()
    logger.info('')
    logger.info('##########################################################')
    logger.info('***** Started http listener *****')
    logger.info('##########################################################')
    logger.info('')

###########################
# Program  begins here
###########################
if __name__ == "__main__":   #Do not run anything below if the file is imported by another program

    # Globals.
    global  httpListener, win , pid, action, workingdir_exists
    httpListener = False             # Indicates if an integral httpListener should be started
    win = False                      # Windows OS
    pid = ''                         # pid for this instance - used for temp filenames
    workingdir_exists = False
    
    setStartValues()       #Default startup global values
    
    init()
      
    startMessages()

    startNow()             #Determine starting action
    
    try:
        if (httpListener):
             startHttpListener(host,port)
    
        nextAction(action)
        
    except KeyboardInterrupt:
        pass   # This is handled as SIGINT

       
