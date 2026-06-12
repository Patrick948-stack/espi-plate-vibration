# import the library used to make python communicate with an instrument
import pyvisa
import time

rm = pyvisa.ResourceManager() #Create a resource manager object that will find the instruments
instrs = rm.list_resources() #A tuple of all the instruments connected
if len(instrs) == 0: 
    print("Sorry, no instrument found!")
else:
    print("Connected instrument(s):")
    print(instrs)
    n = int(input("In the printed tuple, which instrument would you like to open? Pick a number starting from 0 to number of instruments minus 1: "))
    selected_instr = rm.open_resource(instrs[n])
    selected_instr.timeout = 20000 # wait for 20 seconds (20000 milliseconds) for the instrument to respond

    #next two lines ensure that instrument knows when command ends (whenever a \n character is encountered)
    selected_instr.read_termination ='\n'
    selected_instr.write_termination = '\n'
    print("Instrument identity:")
    print(selected_instr.query('*IDN?'))
    #selected_instr.write("C1:OUTP ON")

    #selected_instr.write("C1:OUTP OFF")
    status = selected_instr.query('C1:OUTP?')
    print(f"Signal Generator Status: {status}")

    #Turn on channel 1
    try:
        selected_instr.write('C1:OUTP ON')
        time.sleep(0.5) #Pause moving to next line for 0.5 seconds to give instrument time to relay the message
        changed_status = selected_instr.query('C1:OUTP?')
        print(f"Changed Signal Generator Status: {changed_status.strip()}")
    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")

    
    #Checking information about the waveform on a given channel
    wave_status = selected_instr.query('C1:BSWV?')
    print("\n--- Wave Status--- \n")
    print(wave_status)

    #Changing the waveform to a SQUARE Wave
    try:
        selected_instr.write('C1:BSWV WVTP,SQUare')
        new_status = selected_instr.query('C1:BSWV?')
        if 'WVTP,SQUARE' in new_status:
            print('\n-----Success! The waveform was successfully changed to a square wave ------\n')
            print(f"New wave settings: {new_status}")
        else:
            print('System Failed to Update the Waveform! Bummer!😭')
            print(f"The Device reported: {new_status}")
    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")




    selected_instr.close()




