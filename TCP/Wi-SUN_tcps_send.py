# SPDX-License-Identifier: GPL-3.0
# Copyright (c) 2024,2025 Ryusei Tanaka.
# All Rights Reserved.
# email : s24g354@kagawa-u.ac.jp

import asyncio
from datetime import datetime, timedelta, timezone
import re
import serial_asyncio
import serial
import time

# GPSシリアルポートの設定
ser = serial.Serial('COM8', 9600, timeout=1)

time_diffs = []  # 時間差のリスト

def read_gps_log():
    """GPSログを読み取り、$GPGGA, $GPRMC, $GPGLL のデータが含まれる行を返す"""
    gps_data = ""
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            gps_data += line + "\n"
        if "$GPGGA" in line or "$GPRMC" in line or "$GPGLL" in line:
            return gps_data

# JSTに変換
def convert_to_jst(utc_time):
    """UTCの時刻文字列をJSTに変換（ミリ秒単位まで精度向上）"""
    dt_utc = datetime.strptime(utc_time, "%H%M%S.%f")
    dt_jst = dt_utc + timedelta(hours=9)
    today = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")
    return f"{today} {dt_jst.strftime('%H:%M:%S.%f')[:-3]}"

# 50回の時間差を収集して平均を求める
def calculate_avg_time_diff():
    if not time_diffs:
        return 0.0
    avg_time_diff = sum(time_diffs) / len(time_diffs)
    print(f"平均時間差: {avg_time_diff:.4f} 秒")
    return avg_time_diff

# 50回の計測
for _ in range(50):
    gps_log = read_gps_log()
    times = re.findall(r'\$(?:GPRMC|GPGGA|GPGLL),(\d{6}\.\d+)', gps_log)
    formatted_times = [convert_to_jst(t) for t in times]

    now_time = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    for gps_time in formatted_times:
        dt_now = datetime.strptime(now_time, "%Y-%m-%d %H:%M:%S.%f")
        dt_gps = datetime.strptime(gps_time, "%Y-%m-%d %H:%M:%S.%f")
        time_diff = (dt_now - dt_gps).total_seconds()

        time_diffs.append(time_diff)  # 符号を保持
        print(f"GPS時刻: {gps_time}, PC時刻: {now_time}, 差: {time_diff:.4f} 秒")

    if len(time_diffs) >= 50:
        break

# 平均時間差を計算して出力
Fiftytimes_avg_time_diff = calculate_avg_time_diff()
print(f"Fiftytimes_avg_time_diff: {Fiftytimes_avg_time_diff}")
print(f"現在時刻  :  {datetime.now(timezone.utc) + timedelta(hours=9)}")
print(f"適用時間  :  {datetime.now(timezone.utc) + timedelta(hours=9, seconds=(-Fiftytimes_avg_time_diff))}")
ser.close()

# ユーザー入力
file_suffix = input("ex 0m : ")
chunk_size = int(input("input chunk size  :  "))

data = ''.join(f"{ord(chr(65 + (i % 26))):X}" for i in range(chunk_size * 3500))

async def send_data(port, baudrate, chunk_size, file_suffix, data):
    """非同期でシリアル通信を実行"""
    reader, writer = await serial_asyncio.open_serial_connection(url=port, baudrate=baudrate, limit=32768)
    output_file = f"send_log/tcp_send_data_{file_suffix}_distance_chunk_{chunk_size}Byte.txt"
    sequence_number = 1
    cumulative_data_sent = chunk_size

    try:
        with open(output_file, 'w') as file:
            print(f"Sending data with chunk size: {chunk_size} B")
            print(f"data len: {len(data)}")

            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size - 14]
                sequence_str = f"{sequence_number:06d}"
                data_size_str = f"{len(chunk):05d}"
                send_data = f"{chunk}"
                message = f"{sequence_str}{data_size_str}{send_data}CCC"
                # cumulative_data_sent += chunk_size

                # 時間補正を適用
                corrected_time = datetime.now(timezone.utc) + timedelta(hours=9, seconds=(-Fiftytimes_avg_time_diff))

                for attempt in range(3):  # 最大3回再送
                    writer.write(f"tcps fe80::21d:129f:35c5:2eba {message}\n".encode('utf-8'))
                    current_time = corrected_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    file.write(f"{current_time}, {cumulative_data_sent}, {sequence_number}\n")
                    await writer.drain()

                    try:
                        response = await asyncio.wait_for(wait_for_response(reader, chunk_size), timeout=10)
                        print(f"Response received: {response.strip()}")
                        break  # 成功したらループを抜ける
                    except asyncio.TimeoutError:
                        print(f"Response timeout. Retrying... ({attempt + 1}/3)")

                if attempt == 2:  # 3回の再送がすべて失敗した場合
                    print("Failed to receive response after 3 attempts. Skipping this chunk.")

                sequence_number += 1
                cumulative_data_sent += len(send_data) + 14



                current_time = corrected_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"{current_time}, {cumulative_data_sent}\n")

            print("Data transmission complete.")

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Logging last sent data...")
        with open(output_file, 'a') as file:
            corrected_time = datetime.now(timezone.utc) + timedelta(hours=9, seconds=(-Fiftytimes_avg_time_diff))
            last_time = corrected_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            file.write(f"{last_time}, {cumulative_data_sent}\n")

    finally:
        writer.close()
        await writer.wait_closed()
        print("Serial connection closed.")

async def wait_for_response(reader, chunk_size):
    """レスポンスを非同期で待つ"""
    response = b""
    while b"tcpsd <fe80::21d:129f:35c5:2eba>" not in response:
        response += await reader.read(chunk_size + 100)
    return response.decode('utf-8', errors='ignore')

try:
    asyncio.run(send_data(port="COM4", baudrate=115200, chunk_size=chunk_size, file_suffix=file_suffix, data=data))
except KeyboardInterrupt:
    print("プログラムを終了します")
