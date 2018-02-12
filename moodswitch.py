import gaugette.rotary_encoder
import gaugette.switch
import gaugette.rgbled
import telnetlib
import sys
import time
import math
import re
import RPIO.PWM as PWM

PWM.setup(pulse_incr_us=10, delay_hw=0)
PWM.init_channel(0) # gebruik DMA channel 0

art_host = "192.168.1.5"
art_zone = "1"
art_source = "3"

A_PIN  = 7 #7
B_PIN  = 9 #5
SW_PIN = 8 #3

VP_PIN = 0 #11
VM_PIN = 3 #13
NX_PIN = 2 #15
PV_PIN = 12 #16

LI_PIN = 9  #WPi 13 #Pin 21
LR_PIN = 25 #WPi 6  #Pin 22
LG_PIN = 11 #WPi 14 #Pin 23
LB_PIN = 8  #WPi 10 #Pin 24

led_int = 100#70
led_red = 50#30
led_green = 50#100
led_blue = 50#10

#Set up GPIO
PWM.add_channel_pulse(0, LI_PIN, 0, led_int)
PWM.add_channel_pulse(0, LR_PIN, 0, led_red)
PWM.add_channel_pulse(0, LG_PIN, 0, led_green)
PWM.add_channel_pulse(0, LB_PIN, 0, led_blue)

encoder = gaugette.rotary_encoder.RotaryEncoder(A_PIN, B_PIN)
switch = gaugette.switch.Switch(SW_PIN) #Switch pin
vol_up = gaugette.switch.Switch(VP_PIN) #Vol Up pin
vol_dn = gaugette.switch.Switch(VM_PIN) #Vol Down pin
nxt_pl = gaugette.switch.Switch(NX_PIN) #Next track pin
prv_pl = gaugette.switch.Switch(PV_PIN) #Previous track pin
#led = gaugette.rgbled.RgbLed(LR_PIN,LG_PIN,LB_PIN) #RGB LED

last_state = None
last_switch_state = None
last_delta = 0
last_sequence = encoder.rotation_sequence()
last_heading = 0

toggle_sw = False # 'slot' voor draaiknop push-switch
toggle_vu = False # 'slot' voor volume up push-switch
toggle_vd = False # 'slot' voor volume down push-switch
toggle_nxt = False # 'slot' voor next track push-switch
toggle_prv = False # 'slot' voor previous track push-switch

vol_up_last = None
vol_dn_last = None
nxt_pl_last = None
prv_pl_last = None

vol_up_state = None
vol_dn_state = None
nxt_pl_state = None
prv_pl_state = None

btn_timer = 0 # draaiknop push switch
turncounter = 18

steps_per_cycle = 4 # meestal aantal stappen per detent
remainder = steps_per_cycle//2
counter = 0 # incrementer voor knoppen
mood_val = 2

tn = telnetlib.Telnet(art_host,"5017")
cmd_pwr_on = "*PWR,1,ON;"
cmd_pwr_off = "*PWR,1,OFF;"
cmd_play = "*PLAY,1,SET;"
cmd_pause = "*PAUSE,1;"
cmd_stop = "*STOP;"
cmd_zone_set = "*SRC,1,SET,3;"
cmd_pll_rd = "*SEQ,RD;"
#cmd_nxt_pl = "*PLY,3,SKIP,INC;"
#cmd_prv_pl = "*PLY,3,SKIP,DEC;"

moodseq = ['*SRC,1,SET,1;','*SRC,1,SET,3;','*SRC,1,SET,2;','*SRC,1,SET,6;','*SRC,1,SET,4;']
mood = 1
moodlock = True
lastmood = 2

#pwr_state opvragen bij knop-poweron
tn.write(cmd_pwr_on + "\n") #todo: wachten tot telnet connectie er is
pwr_state = True #todo: true/false opvragen bij ART
tn.write(cmd_zone_set + "\n")
tn.write(cmd_play + "\n")

def updatecolor (led_int, led_red, led_green, led_blue):
    time.sleep(1)
    PWM.clear_channel(0)
    print('Set color using MOOD %1d: Intensity: %1d | Red: %1d | Green: %1d | Blue: %1d' % (mood, led_int, led_red, led_green, led_blue))
    time.sleep(1)
    PWM.add_channel_pulse(0, LI_PIN, 0, led_int)
    PWM.add_channel_pulse(0, LR_PIN, 0, led_red)
    PWM.add_channel_pulse(0, LG_PIN, 0, led_green)
    PWM.add_channel_pulse(0, LB_PIN, 0, led_blue)
    return

def colorswitch (mood_val,lastmood):
    if (mood_val != lastmood):
        if (mood_val == 0):
            updatecolor(0,10,100,100) #red (100)
        if (mood_val == 1): 
            updatecolor(0,10,10,100) #orange (001)
        if (mood_val == 2): 
            updatecolor(0,10,10,100) #yellow (110)
        if (mood_val == 3): 
            updatecolor(0,100,10,100) #green (010)
        if (mood_val == 4):
            updatecolor(0,100,100,10) #blue (001)

        lastmood = mood_val
    return


# Main loop
while True:

    state = encoder.rotation_state()
    switch_state = switch.get_state()
    vol_up_last = vol_up_state
    vol_dn_last = vol_dn_state
    nxt_pl_last = nxt_pl_state
    prv_pl_last = prv_pl_state

    vol_up_state = vol_up.get_state()
    vol_dn_state = vol_dn.get_state()
    nxt_pl_state = nxt_pl.get_state()
    prv_pl_state = prv_pl.get_state()

    #print('Mood: %d' % (mood))

    if (state != last_state or switch_state != last_switch_state or vol_up_last != vol_up_state or vol_dn_last != vol_dn_state or nxt_pl_last != nxt_pl_state or prv_pl_last != prv_pl_state):
        last_switch_state = switch_state
        last_state = state

        # elke 20 lijnen een header
        if last_heading % 20 == 0:
          print ("A B STATE SEQ DELTA CYCLES SWITCH VOL_UP VOL_DN NEXT PREV")
        last_heading += 1

        # signaalbits A en B onttrekken
        a_state = state & 0x01
        b_state = (state & 0x02) >> 1

        # sequentie nr berekenen:
        sequence = (a_state ^ b_state) | b_state << 1

        # verandering delta berekenen:
        delta = (sequence - last_sequence) % 4
        if delta == 3:
            delta = -1
        elif delta==2:
            # gemiste stap achterhalen:
            delta = int(math.copysign(delta, last_delta))
        last_delta = delta
        last_sequence = sequence

        remainder += delta
        cycles = remainder // steps_per_cycle
        remainder %= steps_per_cycle

        print ('%1d %1d %3d %4d %4d %4d %7d %7d %5d %5d %4d' % (a_state, b_state, state, sequence, delta, cycles, switch_state, vol_up_state, vol_dn_state, nxt_pl_state, prv_pl_state))

    ###################################
    # gedrag draaiknop rotary encoder #
    ###################################

    if (delta == 0):
        if (moodlock == False):
            if (mood == 1):
                tn.write('*STOP,1;')
                #time.sleep(1)
            if (mood == 4):
                tn.write('*STOP,4;')
                #time.sleep(1)
            print ('Current sequence: 1%s' % (moodseq[mood]))
            time.sleep(1)
            tn.write(moodseq[mood] + '\n')
            colorswitch(mood,lastmood)
            if (mood == 1):
                tn.write('*PLAY,1,SET;')
            if (mood == 4):
                tn.write('*PLAY,4,SET;')
        delta = 0
        #colorswitch(mood)
        moodlock = True


    if (delta <= -1 and moodlock == True):
        print ('Direction: left') #| Turncounter: %1d' % (turncounter))
        if (mood - 1 < 0): #<=
            mood = 4
            lastmood = 0
        else:
            lastmood = mood
            mood -= 1
        moodlock = False

    if (delta >= 1 and moodlock == True):
        print ('Direction: right') #| Turncounter: %1d' % (turncounter))
        if (mood + 1 > 4):
            mood = 0
            lastmood = 4
        else:
            lastmood = mood
            mood += 1
        moodlock = False


    ###################################
    # gedrag switch in rotary encoder #
    ###################################

    if (switch_state == 1 or toggle_sw == True):
        time.sleep(1) # debounce

	if (switch_state == 1):
            toggle_sw = True
            btn_timer += 1
            print ('btn_timer: %1d' % (btn_timer))

            if (btn_timer > 2 and  toggle_sw == True):
                toggle_sw = False
	if (switch_state == 0):
            toggle_sw = False

    if (switch_state == 0 and toggle_sw == False):
	
        if (btn_timer > 2): # long press
            print ('SWITCH: Power On/Off [long press]')

            #todo: opvragen aan/uit status
            if (pwr_state == False):
                tn.write(cmd_pwr_on + "\n")
                tn.write(cmd_zone_set + "\n")
                print ('sending command')
                #tn.read_until(cmd_pwr_on)
                pwr_state = True

            else:
                tn.write(cmd_stop + "\n")
                tn.write(cmd_pwr_off + "\n")
                #tn.read_until(cmd_pwr_off)
                pwr_state = False

        if (btn_timer > 0 and btn_timer <= 2):
            print ('SWITCH: Play/Pause [short press]')
            # todo: playstatus opvragen om play/pause te beslissen
            tn.write(cmd_play + "\n")
            print ('sending command')
            #tn.read_until(cmd_play)

        btn_timer = 0

    ########################
    # gedrag vol_up button #
    ########################

    if (vol_up_state == 0 or toggle_vu == True):
        time.sleep(1) # debounce

        #if (vol_dn_state == 0 and not toggle_vd == True):

	if (vol_up_state == 0):
            toggle_vu = True

	if (vol_up_state == 1):
            toggle_vu = False
            counter = 0

    if (toggle_vu == True and vol_up_state == 0):
	counter += 3
        print ('VOL UP: +1%d dB' % (counter))
        cmd_vol_up = "*VOL,1,INC," + str(counter) + ";"
        tn.write(cmd_vol_up + "\n")


    ########################
    # gedrag vol_dn button #
    ########################

    if (vol_dn_state == 0 or toggle_vd == True):
        time.sleep(1) # debounce

        if (vol_dn_state == 0):
            toggle_vd = True

        if (vol_dn_state == 1):
            toggle_vd = False
            counter = 0

    if (toggle_vd == True and vol_dn_state == 0):
        counter += 3
        print ('VOL DOWN: -1%d dB' % (counter))
        cmd_vol_dn = "*VOL,1,DEC," + str(counter) + ";"
        tn.write(cmd_vol_dn + "\n")


    ########################
    # gedrag nxt_pl button #
    ########################

    if (nxt_pl_state == 0 or toggle_nxt == True):
        time.sleep(1) # debounce

        if (nxt_pl_state == 0):
            toggle_nxt = True

        if (nxt_pl_state == 1):
            toggle_nxt = False

    if (toggle_nxt == True and nxt_pl_state == 0):
        print ('NEXT TRACK (Mood: %1d)' % (mood))
        if (mood == 1):
            #tn.write("PLY,3,CLR;" + "\n")
            tn.write("*SKIP,1,INC;" + "\n")
            #tn.write("PLY,3,PLAY,SET;" + "\n")
            #break

        if (mood == 4):
            #tn.write("PLY,4,CLR;" + "\n")
            tn.write("*SKIP,2,INC;" + "\n")
            #tn.write("PLY,4,PLAY,SET;" + "\n")
            #break


    ########################
    # gedrag prv_pl button #
    ########################

    if (prv_pl_state == 0 or toggle_prv == True):
        time.sleep(1) # debounce

        if (prv_pl_state == 0):
            toggle_prv = True

        if (prv_pl_state == 1):
            toggle_prv = False

    if (toggle_prv == True and prv_pl_state == 0):
        print ('PREVIOUS PLAYLIST (Mood: %1d)' % (mood))
        if (mood == 1):
            #tn.write("PLY,3,CLR;" + "\n")
            tn.write("*SKIP,1,DEC;" + "\n")
            #tn.write("PLY,4,PLAY,SET;" + "\n")

        if (mood == 4):
            #tn.write("PLY,4,CLR;" + "\n")
            tn.write("*SKIP,2,DEC;" + "\n")
            #tn.write("PLY,4,PLAY,SET;" + "\n")

    #colorswitch(mood,lastmood)

print ('Closing')
tn.close()
PWM.clear_channel(0)
PWM.cleanup()

