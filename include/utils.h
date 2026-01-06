#include <stdlib.h>


// 借用した文字列
typedef struct 
{
    const char *p;
    size_t len;

} RefString;


// 借用した文字列の配列
typedef struct 
{
    RefString* items;
    size_t len;
    
} RefStringArray;


// srcを借用して区切り文字で分割し、srcでのそれぞれの要素の先頭ポインタと長さの配列を返す
RefStringArray split_ref(const char *src, char delim);


// 借用文字列をコピーして所有文字列にする
char *to_cstr(RefString ref_str);


// 所有する文字列の配列
typedef struct 
{
    char** items;
    size_t len;

} OwnStringArray;


// srcを借用して区切り文字で分割し、文字列の配列の所有権を返す
OwnStringArray split_own(const char *src, char delim);


// 解放
void free_own_str_arr(OwnStringArray own_str_arr);


// 文字列から指定の文字を除いたものの所有権を返す
char *remove(const char *src, char c);