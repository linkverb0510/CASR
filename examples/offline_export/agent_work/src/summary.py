def summarize(rows):
    values = [int(row["value"]) for row in rows]
    return {"count": len(values), "total": sum(values)}
