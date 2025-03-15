# SPDX-License-Identifier: GPL-3.0
# Copyright (c) 2024,2025 Ryusei Tanaka.
# All Rights Reserved.
# email : s24g354@kagawa-u.ac.jp

import serial
import serial.tools.list_ports
import os
import sys  # sys.exit() を使用するために追加
from datetime import datetime

# 10GBのバイト数
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB

def serial_read():
    global Serial_Port
    today = datetime.now().strftime("%Y-%m-%d")
    
    def get_new_filename():
        """ 新しいファイル名を生成する """
        return f"Recv_GPS_Data_{today}.txt"

    filename = get_new_filename()
    
    try:
        # データを保存するファイルを開く
        with open(filename, "a") as file:
            while True:
                if Serial_Port != '':
                    data = Serial_Port.readline()
                    data = data.strip()
                    data = data.decode('utf-8')
                    
                    # 現在の時間を取得
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # $GPGGAメッセージ（GPSデータ）を保存
                    if data.startswith('$GPGGA'):
                        log_entry = f"{timestamp} GPS Data: {data}"
                        print(log_entry)
                        file.write(log_entry + '\n')  # ファイルにデータを書き込む
                        file.flush()  # ファイルにすぐ書き込むためにflushする

                    # $GPGSAメッセージ（衛星の状態）をログ出力
                    elif data.startswith('$GPGSA'):
                        log_entry = f"{timestamp} Satellite Status: {data}"
                        print(log_entry)
                        file.write(log_entry + '\n')  # ファイルに衛星状況を保存
                        file.flush()

                    # ファイルサイズを確認し、10GBを超えたらプログラムを終了する
                    if os.path.getsize(filename) > MAX_FILE_SIZE:
                        print(f"{timestamp} File size exceeded 10GB. Exiting program.")
                        sys.exit()  # プログラムを終了
                            
    except KeyboardInterrupt:
        print("\nProgram terminated by user (Ctrl + C)")
        Serial_Port.close()  # Close the serial port when interrupted

# 'COM3' 9600bps Parityなしの場合
Serial_Port = serial.Serial(port='COM8', baudrate=9600)

serial_read()
