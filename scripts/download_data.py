import pandas as pd
import requests
import zipfile
import io
import os
import pyarrow as pa
import pyarrow.parquet as pq

# Configuration
SYMBOL = "BTCUSDT"
# Let's start with just ONE month to test. 
# If this works, you can add "2024-02", "2024-03" back to this list.
MONTHS = ["2024-01"] 
BASE_URL = "https://data.binance.vision/data/spot/monthly/trades"
DATA_DIR = "data/parquet"

os.makedirs(DATA_DIR, exist_ok=True)

for date in MONTHS:
    year, month = date.split("-")
    url = f"{BASE_URL}/{SYMBOL}/{SYMBOL}-trades-{year}-{month}.zip"
    output = f"{DATA_DIR}/{SYMBOL}-{date}.parquet"
    
    if os.path.exists(output):
        print(f"Skipping {date}, already exists.")
        continue

    print(f"Downloading {url}...")
    try:
        r = requests.get(url, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        csv_filename = z.namelist()[0]
        
        print(f"  Processing {date} in chunks (Low RAM mode)...")
        
        with z.open(csv_filename) as f:
            writer = None
            
            # Read CSV in chunks of 500,000 rows (Approx 50MB RAM)
            chunk_iterator = pd.read_csv(
                f, 
                names=["id", "price", "qty", "q_qty", "time", "ibm", "ibm2"], 
                chunksize=500000
            )
            
            for i, chunk in enumerate(chunk_iterator):
                # 1. Optimize Types immediately to save RAM
                df_chunk = chunk[['time', 'price', 'qty', 'ibm']].copy()
                df_chunk['time'] = df_chunk['time'].astype('uint64')
                df_chunk['price'] = df_chunk['price'].astype('float32')
                df_chunk['qty'] = df_chunk['qty'].astype('float32')
                
                # 2. Create Parquet Writer on first chunk
                if writer is None:
                    table = pa.Table.from_pandas(df_chunk)
                    writer = pq.ParquetWriter(output, table.schema)
                
                # 3. Write chunk to disk and clear from RAM
                table = pa.Table.from_pandas(df_chunk)
                writer.write_table(table)
                
                if i % 10 == 0:
                    print(f"    Processed chunk {i}...")

            if writer:
                writer.close()
                
        print(f"  Saved: {output}")
        
    except Exception as e:
        print(f"Failed to process {date}: {e}")