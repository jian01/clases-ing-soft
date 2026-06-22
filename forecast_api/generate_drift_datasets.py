import numpy as np
import pandas as pd

SEED = 42
TEST_PATH = "../data/test.csv"

df = pd.read_csv(TEST_PATH)
features = [c for c in df.columns if c != "Class"]
rng = np.random.default_rng(SEED)



# test_switching.csv: permutación independiente por columna (preserva marginales, rompe correlaciones)
switching_df = df.copy()
X = df[features].values.copy()
for j in range(len(features)):
    X[:, j] = rng.permutation(X[:, j])
switching_df[features] = X
switching_df.to_csv("../data/test_switching.csv", index=False)
print("test_switching.csv generado")


# test_sum.csv: suma la media de cada feature a cada feature
means = df[features].mean()
sum_df = df.copy()
sum_df[features] = df[features] + means
sum_df.to_csv("../data/test_sum.csv", index=False)
print("test_sum.csv generado")


# test_gaussian.csv: ruido gaussiano uniforme (std de cada feature)
# diseñado para mezclarse con test.csv en proporciones crecientes
stds = df[features].std()
gaussian_df = df.copy()
noise = rng.normal(loc=0.0, scale=stds.values, size=(len(df), len(features)))
gaussian_df[features] = df[features].values + noise
gaussian_df.to_csv("../data/test_gaussian.csv", index=False)
print("test_gaussian.csv generado")


# test_v3_bad.csv: corrupción quirúrgica solo en V3 (ruido 10x su std)
v3_bad_df = df.copy()
v3_std = df["V3"].std()
v3_noise = rng.normal(loc=0.0, scale=10 * v3_std, size=len(df))
v3_bad_df["V3"] = df["V3"].values + v3_noise
v3_bad_df.to_csv("../data/test_v3_bad.csv", index=False)
print("test_v3_bad.csv generado")
