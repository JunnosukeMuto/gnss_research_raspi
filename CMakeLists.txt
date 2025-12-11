# 設定
project(gnss_research_raspi LANGUAGES C)
cmake_minimum_required(VERSION 3.10)

# 実行ファイルを定義
add_executable(app main.c)

# ライブラリを定義、　appターゲットにリンク
add_library(gnss i2c.c ntrip.c)
target_link_libraries(app PRIVATE gnss)

# appターゲットはincludeディレクトリをインクルード
target_include_directories(app PRIVATE include)

# C++標準を設定
target_compile_features(app PRIVATE cxx_std_17)