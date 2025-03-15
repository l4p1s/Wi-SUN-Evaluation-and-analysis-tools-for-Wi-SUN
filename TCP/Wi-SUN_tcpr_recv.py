# SPDX-License-Identifier: GPL-3.0
# Copyright (c) 2024,2025 Ryusei Tanaka.
# All Rights Reserved.
# email : s24g354@kagawa-u.ac.jp

import re
import serial
import os
from datetime import datetime, timedelta, timezone

# シリアルポートの設定 (GPS用)
ser_gps = serial.Serial('COM6', 9600, timeout=1)

time_diffs = []  # 時間差のリスト

def read_gps_log():
    gps_data = ""
    while True:
        line = ser_gps.readline().decode('utf-8', errors='ignore').strip()
        if line:
            gps_data += line + "\n"
        if "$GPGGA" in line or "$GPRMC" in line or "$GPGLL" in line:
            return gps_data

# JSTに変換
def convert_to_jst(utc_time):
    dt_utc = datetime.strptime(utc_time, "%H%M%S.%f")
    dt_jst = dt_utc + timedelta(hours=9)
    today = datetime.today().strftime("%Y-%m-%d")
    return f"{today} {dt_jst.strftime('%H:%M:%S.%f')[:-4]}"  # ミリ秒の桁を調整

# 50回の時間差を収集して平均を求める
def calculate_avg_time_diff():
    if len(time_diffs) == 0:
        print("エラー: 計測データがありません。")
        return 0  # ゼロを返すことでエラー回避
    avg_time_diff = sum(time_diffs) / len(time_diffs)
    print(f"平均時間差: {avg_time_diff:.6f} 秒")
    return avg_time_diff

# 50回の計測
for _ in range(50):
    gps_log = read_gps_log()
    times = re.findall(r'\$(?:GPRMC|GPGGA|GPGLL),(\d{6}\.\d{2})', gps_log)
    formatted_times = [convert_to_jst(t) for t in times]

    # 現在のPC時刻を取得
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]

    for gps_time in formatted_times:
        dt_now = datetime.strptime(now_time, "%Y-%m-%d %H:%M:%S.%f")
        dt_gps = datetime.strptime(gps_time, "%Y-%m-%d %H:%M:%S.%f")
        time_diff = (dt_now - dt_gps).total_seconds()

        time_diffs.append(time_diff)
        print(f"GPS時刻: {gps_time}, PC時刻: {now_time}, 差: {time_diff:.6f} 秒")

    if len(time_diffs) >= 50:
        break

# 平88均時間差を計算して出力
print("start")
Fiftytimes_avg_time_diff = calculate_avg_time_diff()
print(f"現在時刻  :  {datetime.now(timezone.utc) + timedelta(hours=9)}")
print(f"適用時間  :  {datetime.now(timezone.utc) + timedelta(hours=9, seconds=(-Fiftytimes_avg_time_diff))}")

# シリアルポートの設定 (データ受信用)
ser = serial.Serial('COM5', 115200, timeout=None)
# ログファイル設定
log_dir = "recv_log"
os.makedirs(log_dir, exist_ok=True)
file_suffix = input("Enter the file suffix (e.g., test1): ")
chunk_size = input("Enter the chunk size (e.g., 1024): ")
log_file = f"{log_dir}/serial_recv_data_{file_suffix}_chunk_{chunk_size}Byte.txt"
raw_log_file = f"{log_dir}/serial_recv_raw_{file_suffix}.txt"

total_data_size = 0

def analyze_packet(recv_data, total_data_size):
    """受信データを解析し、必要な情報をログに記録"""
    pattern = r"tcpr <fe80::21d:129f:35c5:32f1>\s*([0-9a-fA-F]+)"
    match = re.search(pattern, recv_data)
    if match:
        extracted_data = match.group(1)
        sequence_number = extracted_data[:6]  # 最初の6桁をシーケンス番号とする
        data_size = len(extracted_data)
        
        # 時間補正を適用
        corrected_time = datetime.now() - timedelta(seconds=Fiftytimes_avg_time_diff)
        current_time = corrected_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # ミリ秒精度で記録

        # ログデータ作成
        log_entry = f"{current_time},{sequence_number},{data_size}\n"

        # 解析データをログファイルに記録
        with open(log_file, "a") as log:
            log.write(log_entry)

        print(f"取り出したデータ: {extracted_data}")
        print(f"時刻: {current_time}, シーケンス番号: {sequence_number}, データサイズ: {data_size}")

        total_data_size += data_size
        print(f"総データの長さ: {total_data_size}")
    return total_data_size

while True:
    if ser.in_waiting > 0:
        rcv_data = ser.readline(2048).decode('ascii', errors='ignore').strip()

        # PCの時間補正 (GPSとの差分を考慮)
        corrected_time = datetime.now() - timedelta(seconds=Fiftytimes_avg_time_diff)
        current_time = corrected_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # 受信データをそのままログに記録
        with open(raw_log_file, "a") as raw_log:
            raw_log.write(f"{current_time}, {rcv_data}\n")

        total_data_size = analyze_packet(rcv_data, total_data_size)
        print(rcv_data)