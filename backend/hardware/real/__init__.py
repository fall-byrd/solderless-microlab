# TODO: Need to add in real code to control device here

import time
import config
import serial
import RPi.GPIO as GPIO


def serReadUntil(ser, expected):
    """
    Read from a serial port until the expected text appears

    :param ser:
        The serial port to read from
    :param expected:
        The expected string
    :return:
        The last line read
    """
    line = ""
    while(not(expected in str(line))):
        line = ser.readline()
    return line


# Init timer for secondsSinceStart()
timer = time.time()
initialized = False
tempSer = None
grblSer = None

RELAY_ON = True
RELAY_OFF = False


def initHardware():
    """
    Initialize the hardware.

    Can't do this in the general module code as both flask and celery include this module
    and we don't want to open up the serial ports on flask.

    :return:
    None
    """
    global tempSer, grblSer, initialized

    if not initialized:
        # Init serial port for temp sensor
        tempSer = serial.Serial(config.hardwareTempPort,timeout=0.5)

        # Init relays
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(config.hardwareHeaterPumpPin, GPIO.OUT)
        GPIO.setup(config.hardwareHeaterPin, GPIO.OUT)
        GPIO.setup(config.hardwareCoolerPin, GPIO.OUT)
        GPIO.setup(config.hardwareStirrerPin, GPIO.OUT)

        GPIO.output(config.hardwareHeaterPumpPin, RELAY_OFF)
        GPIO.output(config.hardwareHeaterPin, RELAY_OFF)
        GPIO.output(config.hardwareCoolerPin, RELAY_OFF)
        GPIO.output(config.hardwareStirrerPin, RELAY_OFF)

        # Init serial port for grbl sensor
        grblSer = serial.Serial(config.hardwareArduinoPort, 115200, timeout=1)

        # configure the syringe pumps
        for axis, syringeConfig in config.syringePumpsConfig.items():
            stepsPerMM = syringeConfig['stepsPerRev']/syringeConfig['mmPerRev']
            axisToCNCID = {
                "X": "0",
                "Y": "1",
                "Z": "2",
            }
            #configure steps/mm
            grblWrite('$10{0}={1}\n'.format(axisToCNCID[axis], stepsPerMM))
            #configure max mm/min
            grblWrite('$11{0}={1}\n'.format(axisToCNCID[axis], syringeConfig['maxmmPerMin']))
        initialized = True


def log(message):
    print('harware.simulation - ' + str(message))

def secondSinceStart():
    """
    The number of seconds since this package was started.

    This method is modified in the simulation package to allow for speeding up time without modifying the recipes.

    :return:
    The number of seconds since this package was started.
    """
    elapsed = time.time() - timer
    return elapsed


def sleep(seconds):
    """
    Sleep for a number of seconds.

    This method is modified in the simulation package to allow for speeding up time without modifying the recipes.

    :param seconds:
    Number of seconds to sleep.

    :return:
    None
    """
    time.sleep(seconds)

def grblWrite(command):
    """
    Writes the given command to grbl. 

    :param command:
    String of grbl command to execute

    :return:
    None
    """
    global grblSer
    grblSer.reset_input_buffer()
    grblSer.write(bytes(command, 'utf-8'))
    # Grbl will execute commands in serial as soon as the previous is completed.
    # No need to wait until previous commands are complete. Ok only signifies that it
    # parsed the command
    response = grblSer.read_until()
    if 'error' in str(response):
        raise Exception("grbl command error: {0}".format(response))


def turnHeaterOn():
    """
    Turns heater on.

    :return:
    None
    """
    initHardware()
    GPIO.output(config.hardwareHeaterPin, RELAY_ON)
    GPIO.output(config.hardwareHeaterPumpPin, RELAY_ON)


def turnHeaterOff():
    """
    Turns heater off.

    :return:
    None
    """
    initHardware()
    GPIO.output(config.hardwareHeaterPin, RELAY_OFF)
    GPIO.output(config.hardwareHeaterPumpPin, RELAY_OFF)


def turnCoolerOn():
    """
    Turn cooler on.

    :return:
    None
    """
    initHardware()
    GPIO.output(config.hardwareCoolerPin, RELAY_ON)


def turnCoolerOff():
    """
    Turn cooler off.

    :return:
    None
    """
    initHardware()
    GPIO.output(config.hardwareCoolerPin, RELAY_OFF)


def getTemp():
    """
    Read the temperature from the temperature sensor.
    :return:
    The temperature of the temperature sensor.
    """
    initHardware()

    line = "12345678901"
    lastLine = ""
    while (len(line) > 10):
        lastLine = line
        line = tempSer.readline()
        print('ser read ' + str(len(line)) + ' ' + str(line) )

    lastLine = str(lastLine)
    start = lastLine.find('t1=') + len('t1=')
    end = lastLine.find(' ',start)
    print('found ' + str(start) + ' ' + str(end) + ' ' + lastLine)
    temperature = float(lastLine[start:end])

    print('Read temperature ' + str(temperature)) # + ' ' + str(lastLine))
    return temperature


def turnStirrerOn():
    """
    Turns the stirrer on.

    :return:
    None
    """
    initHardware()
    GPIO.output(config.hardwareStirrerPin, RELAY_ON)


def turnStirrerOff():
    """
    Turns the stirrer off.

    :return:
    None
    """
    initHardware()
    GPIO.output(config.hardwareStirrerPin, RELAY_OFF)


def pumpDispense(pumpId, volume):
    """
    Dispense reagent from a syringe

    :param pumpId:
        The pump id. One of 'X' or 'Y'
    :param volume:
        The number of ml to dispense
    :return:
        None
    """
    global grblSer

    initHardware()
    maxmmPerMin = config.syringePumpsConfig[pumpId]['maxmmPerMin']
    mmPerml = config.syringePumpsConfig[pumpId]['mmPerml']
    totalmm = volume*mmPerml
    grblWrite('G91{0}{1}\n'.format(pumpId, totalmm))

    # sleep for estimated dispense time, plus one second to account for (de)acceleration of the motor
    time.sleep(abs(totalmm)/maxmmPerMin*60 + 1)


