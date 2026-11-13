import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error

# 1. 데이터 불러오기 (연도, 게임수, 에버리지 열이 있다고 가정)
df = pd.read_csv('data/bowling_avg.csv')

# 전처리: 규정 게임 수 미만 결측치/이상치 제거 (예: 30게임 이상만 남기기)
df = df[df['게임수'] >= 30].dropna()

X = df[['연도']]
y = df['에버리지']

# 2. 베이스라인 (전체 연도 평균 모델)
baseline_pred = np.full_like(y, y.mean(), dtype=float)
print("베이스라인 MAE:", mean_absolute_error(y, baseline_pred))

# 3. 선형 회귀 모델 학습
model = LinearRegression()
model.fit(X, y)
pred = model.predict(X)

print(f"연도별 에버리지 변화 기울기: {model.coef_[0]:.4f}")
print("회귀 모델 R2:", r2_score(y, pred))
print("회귀 모델 MAE:", mean_absolute_error(y, pred))
