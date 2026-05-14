"""
Simulated Lambda: 3GPP Change Detector.
In production: Triggered by EventBridge, polls 3GPP FTP servers.
"""

import os
import ftplib


def lambda_handler(event=None, context=None):
    ftp_host = os.getenv("FTP_HOST", "ftp.3gpp.org")
    raw_bucket = os.getenv("RAW_BUCKET", "./data/raw")
    os.makedirs(raw_bucket, exist_ok=True)

    try:
        ftp = ftplib.FTP(ftp_host)
        ftp.login()
        ftp.cwd("/Specs/archive")
        releases = ftp.nlst()
        print(f"Found {len(releases)} releases")

        for release in releases[-3:]:
            ftp.cwd(f"/Specs/archive/{release}")
            files = ftp.nlst()
            for f in files[:5]:
                local_path = os.path.join(raw_bucket, release, f)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                if not os.path.exists(local_path):
                    print(f"📥 Downloading: {release}/{f}")
                    with open(local_path, "wb") as fp:
                        ftp.retrbinary(f"RETR {f}", fp.write)
        ftp.quit()
        return {"statusCode": 200, "body": "Sync complete"}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}


if __name__ == "__main__":
    lambda_handler()
