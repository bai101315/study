import sys

def check(arrs):
    a, b, c, x, y, z = arrs
    return a + b > c and x + y > z

def subsets(arrs):
    n = len(arrs)
    path = []
    found = False

    # 枚举每个位置，放arrs中的数字
    def dfs(i):
        # nonlocal found
        # if found:
        #     return
        print(path.copy())
        if len(path) == n:
            
            if check(path):
                found = True
        for j in range(i, n):
            path.append(arrs[j])
            dfs(j+1)
            path.pop()
    
    dfs(0)
    return found

def solve():
    arrs = list(map(int, input().split()))
    arrs.sort()
    # 练一下回溯
    ans = subsets(arrs)
    if not ans:
        print("No")
    else:
        print("Yes")

if __name__ == "__main__":
    t = int(input())
    for _ in range(t):
        solve()
