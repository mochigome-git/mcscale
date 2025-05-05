import serial    #    PySerial

dev = "/dev/ttyUSB0"    #    デバイス名
rate = 9600    #    レート (bps)
ser = serial.Serial(dev, rate, timeout=10)

# string = "Hello World"
# string = string + "\r\n"    #    ターミネーターを付ける
# ser.write(string)    #    コマンド送信

res = ser.readline()    #    コマンド受信
res = res.encode()    #    エンコード
print(res)
