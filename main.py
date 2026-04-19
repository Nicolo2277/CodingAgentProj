from src.llm.factory import get_client
from src.llm.tasks.find_bugs import find_bugs


SAMPLE_CODE = """
def divide(numbers, divisor):
    results = []
    for i in range(len(numbers)):
        result = numbers[i] / divisor
        results.append(result)
    return results

def get_user(users, id):
    for i in range(len(users)):
        if users[i]["id"] = id:
            return users[i]
    return None
"""

if __name__ == "__main__":
    client = get_client()
    report = find_bugs(SAMPLE_CODE, client)

    print(f"\n{'='*40}")
    print(f"Trovati {len(report.bugs)} bug\n")
    for bug in report.bugs:
        print(f"  [{bug.severity.upper()}] Linea {bug.line}: {bug.description}")
        print(f"  Fix: {bug.fix}\n")
    print(f"Sommario: {report.summary}")