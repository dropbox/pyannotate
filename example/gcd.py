def main():
    print(gcd(15, 10))
    print(gcd(45, 12))

def gcd(a, b):
    while b:
        a, b = b, a%b
    return a
