#include <stdlib.h>
#include <string.h>
#include "utils.h"
#include "ntrip.h"

#define ST_NUM_OF_PARAMS 18
#define ST_TYPE 0
#define ST_MOUNTPOINT 1
#define ST_LAT 9
#define ST_LON 10


SourceTable parse_sourcetable(const char* source_table, SourceTableType type)
{
    SourceTable table = {0};

    // CRLFをLFにする
    char *lf_str = remove(source_table, '\r');
    OwnStringArray lines = split_own(lf_str, '\n');

    // 行ごとに
    for (size_t i = 0; i < lines.len; i++)
    {
        RefStringArray fields = split_ref(lines.items[i], ';');

        // フィールドの数が規定の数より小さければ除外
        if (fields.len < ST_NUM_OF_PARAMS) { table.len--; continue; }

        // typeはstreamでないと除外
        char *table_type = to_cstr(fields.items[ST_TYPE]);
        if (*table_type != "STR") { table.len--; continue; }

        // mountpointが空か、100文字を超えていたら除外
        if (fields.items[ST_MOUNTPOINT].len > 100 ||
            fields.items[ST_MOUNTPOINT].len == 0) { table.len--; continue; }

        char *lat_end, *lon_end;
        char *lat_start = to_cstr(fields.items[ST_LAT]);
        char *lon_start = to_cstr(fields.items[ST_LON]);
        double lat = strtod(lat_start, lat_end);
        double lon = strtod(lon_start, lon_end);

        // 緯度、経度の文字列が完全に数値に変換できなければ除外
        if (lat_end == lat_start || *lat_end != '\0') { table.len--; continue; }
        if (lon_end == lon_start || *lon_end != '\0') { table.len--; continue; }
        
    }
    
}