import hashlib


def checksum_rows(rows):
    payload = "|".join(f"{row['name']}={row['value']}" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
