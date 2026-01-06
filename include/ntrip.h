#include <stdlib.h> 

// source-tableから必要な要素を抜き出した構造体
typedef struct
{
    char mountpoint[101];
    float latitude;
    float longitude;

} SourceTableRecord;


typedef enum
{
    STR,
    CAS,
    NET

} SourceTableType;


int compare_st_type(SourceTableType type, const char *str)
{
    switch (type)
    {
    case STR:
    {
        if (str[0] == 'S' && str[1] == 'T' && str[2] == 'R') return 1;
        else return 0;
    }

    case CAS:
    {
        if (str[0] == 'C' && str[1] == 'A' && str[2] == 'S') return 1;
        else return 0;
    }

    case NET:
    {
        if (str[0] == 'N' && str[1] == 'E' && str[2] == 'T') return 1;
        else return 0;
    }
    
    default: return 0;
    }
}


// source-tableの要素を格納する構造体
typedef struct
{
    SourceTableRecord* records;
    size_t len;

} SourceTable;


// source-tableをパースして、絞り込む
SourceTable parse_source_table(const char* source_table, SourceTableType type);