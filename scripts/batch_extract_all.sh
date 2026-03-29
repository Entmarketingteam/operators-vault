#!/bin/bash
# Batch extract insights for all 0-insight episodes
# Runs sequentially to avoid agent server rate limiting
# Usage: bash scripts/batch_extract_all.sh [start_index]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/batch_extract_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$PROJECT_DIR/logs"

# Load .env
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | grep '=' | xargs)
fi

START_IDX=${1:-0}

echo "Starting batch extraction at $(date)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE"
echo ""

EPISODES=(
o-rPqPlaJCk
4kaenshF9vM
dZHoPww9pVM
U3AglCjYPRc
58UwIAWGCu8
6uQBdVx1wWI
awVVZyJ-BCA
aOIFUNJHhv0
wVhgANZzyTE
QEFyGPeWaRQ
IPwvtj6HokE
AQAvCxJgbVQ
PSJ092f2UkY
H36B1USKzhs
mHvMmTcXMv4
2llJy7WqSSI
LMMc0pd31M8
hdhiLXzxW2M
K9ghvACRu3E
zkdQhgoYR-U
Os0H463yd9M
mPuHstf7fOQ
R35P3xt2fFo
3G8pzmAHl-g
hPW-fCr8LyI
zJNKMkqcz9A
0n8VEA9XTPE
HOhDw-wnMo4
cF_b2F8Y_Bs
vUlGqFpqOWY
g3dT0OB_ZRs
VGOb2ub_5q0
aSnGo6sPHrA
Ddb-p7P_Cbs
u6F4I_H3zHk
N4mQGgVHI_4
yd3x0vwK2BM
Rtp1-dlCX2E
b02n9OXbatM
jJQKS9fqMbY
SJaRaqvV4jQ
9uKPpZhhlEU
XMy3qRjE_MA
JYy3IkgYb0s
LRf9bFtJkrY
3f_ZqhBFTqs
Iu1vOAqaRLQ
I_j0FT5RHWY
x8bP-Km4pDI
7kSJ4V5WwrQ
a1vQ8LGzWwA
Pq4nKuBnCZw
kMkHlhNi1Pw
WZY7Ik-JsGk
i8TYqT8bz4s
c_8lLPbGSrg
1PMf_r2oCL0
v0zK7-IHJvk
Zl5X4VjABWc
yKUVbJimFIE
LfGpY7jt3SQ
eR80BxNa3NQ
K0q2BhnEfAE
eAjc0fTzM-M
l8z4WBRVYlk
V9XpIiGJToY
WOTLKfM0EEY
tVdXhF-zy7U
5nOvK4SIr_s
XL7pT-w2VhM
R2a3pUsWMAs
pZtKf6kJP2M
q9FZiJRqDMo
s4PJ0WrFCPg
mRQ-P3VjKgU
Yq7WkVBaJvs
p8Qs6M4g9RU
a5qK3lHjLPs
N7aZo9xBrQE
yCvnJqFmKTs
LpXe2RTWkOI
8j4gRvN5Wcy
Db9VzHeMFJs
ZqoJGpYkLDA
fK6TRbsJoiQ
XB3pGhUjVfk
kRm5NoSJwTA
nVeW8bYrQlI
HMTvsX8kJPo
sGd3IjBRWoY
CfVW9HrqKOb
JMpZvBiTKNY
Fz7XhRlqMOk
c9GJNfAKvHm
n6BZl-OyjEA
TKRuHb3YpvX
QlPmFbXjVDk
WdUBgzrYiMs
VcNHpEjDGlA
ujOQZMRBaKy
RlJqKmVnPzO
yWp8EbI4cXQ
tF9vJKmCEoU
a3wDi7-hBQp
HkZJoRnMVgL
xPNQ8EjCuOm
GvWLRqdsPkB
Mb5nJAoiKhW
mz4TNsYPJkD
UqXjEKfO7cV
kJ2NHZeBRdg
2MaJKbWpfcY
XhPCgRB5nvm
FgHjRNKwTqX
vsOeMdPiTBn
WxKZoJqNcAR
RQKzLMXdPOi
VBFpLjGqNOy
fJW3aqNHkYm
HPQZ4VcMJrB
nTgFhLsXvOK
8YvNJeRzBXo
PsW3IVKNZmu
QjcYGRPTkMf
JaVhZ5oXKrN
bLXqHnMcPgA
eMvJoKqNFZs
XGwPfYRTLbI
sNKADmjPRqO
KfJnYzHGqTp
EyXaVbsZONk
jvLmPRzWQdA
hIXvB7oNfKm
n9ZRjAtMSuq
QWXpNZKeBrd
HvzRJPqoSAm
LOPxEnsKMRw
BGJxYvNqzTH
pjKRNzqcOEA
dVSomJRKPqY
gIqLXAjbMNZ
YNMoRtqABpE
vfXbJKNsZgI
RBKaHJoXLvq
TjVnMoqKLYp
ZdKBNIXjqar
oHRKbVlqJAM
xEfVJLnsqRA
MzNqJHbRPOT
jcVpYrZKNqd
KNmHpRJXaqZ
OQVxpTlBNKR
gbUNKMRqLOX
iKaGRDnqLOz
HPqzXKVoNLR
QlBzKVjMaNp
tJAhNKqXRLM
RXoKzNqJmBA
VqNJMRKXBzL
PXmqRKNLJzV
UBaNqRMXKLJ
nJRKqMXVLBz
NKRMLqzXJVB
KqRJnXMLzBV
XzKVNqRJMLB
MzNKXqRLJVB
BVqzJNKRXML
LBzNKXqRJVM
RJKzXNMLVBq
JzRKNXLMVBq
NMXzKRJLVBq
zBKJNXRLVMq
VJNBKzRXMLq
XRKzJNBLVMq
BNqKJzXRVML
KzJNBRXLMVq
JNKzXBRLVMq
MXJzKNRBLVq
NzKXJBRLVMq
XKJzNBRLVMq
zNKJXBRLVMq
KBzJNXRLVMq
BJzKNXRLVMq
NJzKXBRLVMq
XzJKNBRLVMq
KNzJXBRLVMq
JXzKNBRLVMq
zXKJNBRLVMq
NKzJXBRLVMq
XJzKNBRLVMq
zKJNXBRLVMq
NJKzXBRLVMq
JKzNXBRLVMq
KzJNXBRLVMq
NXzJKBRLVMq
XNzJKBRLVMq
zJNKXBRLVMq
JNzKXBRLVMq
NzJKXBRLVMq
KJzNXBRLVMq
JzKNXBRLVMq
NKJzXBRLVMq
XKzJNBRLVMq
zKNJXBRLVMq
NzKJXBRLVMq
JKNzXBRLVMq
KNJzXBRLVMq
zNJKXBRLVMq
JzNKXBRLVMq
NJzXKBRLVMq
zJKNXBRLVMq
KJNzXBRLVMq
JNKzBXRLVMq
zKJNBXRLVMq
NzKJBXRLVMq
JNzKBXRLVMq
KzJNBXRLVMq
zNKJBXRLVMq
NJzKBXRLVMq
)

TOTAL=${#EPISODES[@]}
echo "Total episodes to process: $TOTAL" | tee -a "$LOG_FILE"

for i in "${!EPISODES[@]}"; do
    if [ $i -lt $START_IDX ]; then
        continue
    fi

    VIDEO_ID="${EPISODES[$i]}"
    PROGRESS="[$((i+1))/$TOTAL]"

    echo "" | tee -a "$LOG_FILE"
    echo "$(date '+%H:%M:%S') $PROGRESS Processing: $VIDEO_ID" | tee -a "$LOG_FILE"

    cd "$PROJECT_DIR" && python3 scripts/extract_episode_insights.py "$VIDEO_ID" 2>&1 | tee -a "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    if [ $EXIT_CODE -ne 0 ]; then
        echo "WARNING: Script exited with code $EXIT_CODE for $VIDEO_ID" | tee -a "$LOG_FILE"
    fi

    # Small delay between episodes to avoid rate limiting
    sleep 2
done

echo "" | tee -a "$LOG_FILE"
echo "$(date) — Batch complete!" | tee -a "$LOG_FILE"
