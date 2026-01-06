#include <stdlib.h>
#include <string.h>
#include "utils.h"


RefStringArray split_ref(const char *src, char delim)
{
  RefStringArray arr = {0};
  size_t len = 1;

  // 一文字ずつループ
  // 何個に分割されたかを数える
  for (const char* pch = src; *pch; pch++)
  {
    if (*pch == delim) len++;
  }
  
  // 数えた個数を格納・配列の領域をmalloc
  arr.len = len;
  arr.items = malloc(sizeof(RefString) * len);
  if (arr.items == NULL) return arr;

  size_t idx = 0;
  const char* current_item_ptr = src;

  // 一文字ずつ
  for (const char* pch = src; ; pch++)
  {
    // 区切り文字かヌル文字だったら
    if (*pch == delim || *pch == '\0')
    {
      arr.items[idx] = (RefString)
      {
        .p = current_item_ptr,
        .len = pch - current_item_ptr,
      };

      // 次の要素の開始ポインタに更新、arrのインデックスを更新
      current_item_ptr = pch + 1;
      idx++;

      // ヌル文字ならループ終了
      if (*pch == '\0') break;
    }
  }

  return arr;
}


char *to_cstr(RefString ref_str)
{
  // ヌル文字の分も確保
  char *p = malloc(ref_str.len + 1);
  if (ref_str.len != 0) memcpy(p, ref_str.p, ref_str.len);
  p[ref_str.len] = '\0';
  return p;
}


OwnStringArray split_own(const char *src, char delim)
{
  OwnStringArray arr = {0};
  size_t len = 1;

  // 一文字ずつループ
  // 何個に分割されたかを数える
  for (const char* pch = src; *pch; pch++)
  {
    if (*pch == delim) len++;
  }

  // 数えた個数を格納
  arr.len = len;

  size_t idx = 0;
  const char* current_item_ptr = src;

  // 一文字ずつ
  for (const char* pch = src; ; pch++)
  {
    // 区切り文字かヌル文字なら
    if (*pch == delim || *pch == '\0')
    {
      // lenはヌル文字を含まない長さ
      size_t str_len = pch - current_item_ptr;

      // 要素一つずつmallocしてsrcの内容をmemcpyしていく
      arr.items[idx] = malloc(len + 1);
      if (str_len != 0) memcpy(arr.items[idx], current_item_ptr, str_len);
      arr.items[idx][len] = '\0';

      // 次の要素の開始ポインタに更新、arrのインデックスを更新
      current_item_ptr = pch + 1;
      idx++;

      // ヌル文字ならループ終了
      if (*pch == '\0') break;
    }
  }

  return arr;
}


void free_own_str_arr(OwnStringArray own_str_arr)
{
  for (size_t i = 0; i < own_str_arr.len; i++)
  {
    free(own_str_arr.items[i]);
  }
}


char *remove(const char *src, char c)
{
  char *str;
  size_t count = 0;
  size_t len = 0;

  // 一文字ずつループ
  // 除去する文字がいくつ含まれるか、srcがnull文字を除いて何文字かを数える
  for (const char* pch = src; *pch; pch++)
  {
    if (*pch == c) count++;
    len++;
  }

  // 元の文字列の長さ-除去する文字の数+null文字
  str = malloc(len - count + 1);

  size_t idx = 0;
  
  // 一文字ずつ
  for (const char* pch = src; *pch; pch++)
  {
    if (*pch == c) continue;
    str[idx] = *pch;

    idx++;
  }

  str[len - count] = '\n';
  return str;
}