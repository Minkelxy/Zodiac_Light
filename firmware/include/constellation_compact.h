/* Generated compact scene: structure-of-arrays, checked integer ranges.
 * Positions and lengths: stored / 10 millimetres; magnitude: stored / 100.
 * u: stored / 65535 (both endpoints exact); it is not a /65536 Q0.16 value.
 * Quantization: nearest integer, half-way cases away from zero; no clamping.
 * LED array index is the WS2812 serial address. Members need not be contiguous.
 * CSR neighbours for star s occupy [adjacency_offsets[s], offsets[s+1]).
 * Neighbour entries pair with adjacency_edge_index in original edge order.
 * Non-edge u is unused (0), hidden owner is UINT16_MAX, missing mag is INT16_MIN.
 * Array byte counts exclude linker alignment; flash/RAM placement is target-specific.
 * Empty arrays have one storage sentinel, which must not be iterated.
 * This header can coexist with the original float scene header.
 */
#ifndef CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H
#define CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H

#include <stdint.h>

#define CONSTELLATION_COMPACT_OWNER_NONE UINT16_MAX
#define CONSTELLATION_COMPACT_MAG_MISSING INT16_MIN
#define CONSTELLATION_COMPACT_LED_HIDDEN 0u
#define CONSTELLATION_COMPACT_LED_STAR 1u
#define CONSTELLATION_COMPACT_LED_EDGE 2u
#define CONSTELLATION_COMPACT_LED_COUNT 268u
#define CONSTELLATION_COMPACT_STAR_COUNT 21u
#define CONSTELLATION_COMPACT_EDGE_COUNT 24u
#define CONSTELLATION_COMPACT_STAR_LED_INDEX_COUNT 84u
#define CONSTELLATION_COMPACT_EDGE_LED_INDEX_COUNT 184u
#define CONSTELLATION_COMPACT_ADJACENCY_COUNT 48u
#define CONSTELLATION_COMPACT_ADJACENCY_OFFSET_COUNT 22u
#define CONSTELLATION_COMPACT_POSITION_SCALE 10u
#define CONSTELLATION_COMPACT_LENGTH_SCALE 10u
#define CONSTELLATION_COMPACT_MAGNITUDE_SCALE 100u
#define CONSTELLATION_COMPACT_U_DENOMINATOR 65535u
#define CONSTELLATION_COMPACT_TABLE_BYTES 3718u
#define CONSTELLATION_COMPACT_C_ARRAYS_BYTES 3718u
#define CONSTELLATION_COMPACT_RGB_FRAME_BYTES 804u
#define CONSTELLATION_COMPACT_SCENE_SHA256 "cbb22e7d6cb0240b4415df78731b6c5fb75a2fd1fa8f78b6add998e3c289e910"

static const int16_t constellation_compact_led_x_dm[268] = {
    768, 818, 818, 768, 901, 948, 1031, 1081, 1081, 1031, 1185, 1231,
    1276, 1322, 1426, 1476, 1517, 1546, 1587, 1637, 1637, 1587, 1675, 1695,
    1716, 1736, 1757, 1777, 1798, 1818, 1856, 1906, 1993, 2042, 2128, 2178,
    2278, 2328, 2378, 2427, 2477, 2526, 2576, 2626, 2675, 2725, 2825, 2875,
    2973, 3022, 3071, 3120, 3218, 3268, 3268, 3218, 3319, 3348, 3378, 3408,
    3437, 3467, 3497, 3526, 3577, 3627, 3627, 3577, 3189, 3169, 3149, 3129,
    3109, 3089, 3069, 3048, 3028, 3008, 2933, 2924, 2915, 2906, 2898, 2889,
    2880, 2871, 2875, 2825, 2764, 2733, 2703, 2673, 2643, 2613, 2551, 2501,
    2431, 2395, 2358, 2321, 2285, 2248, 2178, 2128, 2088, 2066, 2043, 2020,
    1997, 1974, 1951, 1929, 1889, 1839, 1781, 1745, 1687, 1637, 1524, 1474,
    1424, 1375, 1325, 1275, 1225, 1175, 1125, 1076, 1026, 976, 863, 813,
    813, 863, 760, 734, 708, 683, 657, 631, 605, 579, 553, 528,
    502, 476, 423, 373, 373, 423, 473, 500, 527, 553, 580, 607,
    634, 660, 687, 714, 740, 767, 794, 821, 871, 921, 921, 871,
    987, 1017, 1047, 1076, 1106, 1135, 1165, 1194, 1224, 1253, 1283, 1313,
    1379, 1429, 1507, 1541, 1574, 1608, 1642, 1676, 1710, 1743, 1777, 1811,
    1888, 1938, 1938, 1888, 2143, 2193, 2193, 2143, 2009, 1959, 1910, 1860,
    1811, 1761, 1712, 1662, 1613, 1563, 1429, 1379, 1839, 1889, 1986, 2035,
    2085, 2135, 2185, 2235, 2284, 2334, 2384, 2434, 2484, 2533, 2583, 2633,
    2683, 2733, 2782, 2832, 2929, 2979, 2979, 2929, 3042, 3074, 3137, 3187,
    3187, 3137, 2551, 2501, 2561, 2572, 2584, 2596, 2607, 2619, 2630, 2642,
    2653, 2665, 2675, 2725, 2725, 2675, 1906, 1856, 1814, 1786, 1758, 1730,
    1687, 1637, 1476, 1426
};

static const int16_t constellation_compact_led_y_dm[268] = {
    586, 586, 656, 656, 656, 672, 673, 673, 743, 743, 766, 787,
    808, 828, 852, 852, 794, 754, 697, 697, 627, 627, 802, 848,
    893, 939, 984, 1030, 1076, 1121, 1226, 1226, 1241, 1232, 1247, 1247,
    1227, 1233, 1239, 1244, 1250, 1256, 1262, 1268, 1274, 1280, 1260, 1260,
    1269, 1259, 1249, 1239, 1249, 1249, 1179, 1179, 1112, 1071, 1031, 991,
    951, 910, 870, 830, 763, 763, 693, 693, 1337, 1383, 1429, 1475,
    1520, 1566, 1612, 1658, 1703, 1749, 1756, 1707, 1657, 1608, 1559, 1510,
    1461, 1411, 1330, 1330, 1180, 1140, 1101, 1061, 1021, 981, 902, 902,
    954, 988, 1022, 1056, 1090, 1124, 1177, 1177, 1339, 1383, 1428, 1472,
    1516, 1561, 1605, 1650, 1741, 1741, 1699, 1665, 1622, 1622, 1598, 1602,
    1606, 1610, 1614, 1618, 1622, 1626, 1630, 1634, 1638, 1642, 1618, 1618,
    1688, 1688, 1782, 1825, 1867, 1910, 1953, 1996, 2039, 2082, 2124, 2167,
    2210, 2253, 2347, 2347, 2417, 2417, 2500, 2542, 2585, 2627, 2669, 2711,
    2754, 2796, 2838, 2880, 2923, 2965, 3007, 3050, 3133, 3133, 3203, 3203,
    3293, 3334, 3374, 3414, 3454, 3495, 3535, 3575, 3616, 3656, 3696, 3737,
    3827, 3827, 3750, 3713, 3676, 3640, 3603, 3566, 3529, 3492, 3455, 3418,
    3342, 3342, 3272, 3272, 3723, 3723, 3793, 3793, 3779, 3786, 3793, 3800,
    3806, 3813, 3820, 3827, 3834, 3840, 3897, 3897, 1811, 1811, 1787, 1792,
    1796, 1800, 1805, 1809, 1814, 1818, 1822, 1827, 1831, 1836, 1840, 1844,
    1849, 1853, 1858, 1862, 1838, 1838, 1908, 1908, 1975, 2013, 2081, 2081,
    2151, 2151, 832, 832, 721, 673, 624, 575, 527, 478, 429, 381,
    332, 284, 173, 173, 103, 103, 1296, 1296, 1362, 1404, 1445, 1487,
    1552, 1552, 922, 922
};

static const uint8_t constellation_compact_led_owner_type[268] = {
    1u, 1u, 1u, 1u, 2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u,
    2u, 2u, 1u, 1u, 2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u, 2u, 2u, 1u, 1u,
    2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u,
    2u, 2u, 2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u,
    2u, 2u, 1u, 1u, 2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u,
    2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 1u, 1u, 2u, 2u, 1u, 1u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u,
    1u, 1u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u,
    2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u, 1u, 1u,
    2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u,
    1u, 1u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u,
    1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 1u, 1u, 1u, 1u, 2u, 2u, 1u, 1u,
    1u, 1u, 1u, 1u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u,
    2u, 2u, 1u, 1u, 1u, 1u, 1u, 1u, 2u, 2u, 2u, 2u,
    1u, 1u, 1u, 1u
};

static const uint16_t constellation_compact_led_owner_index[268] = {
    0u, 0u, 0u, 0u, 17u, 17u, 1u, 1u, 1u, 1u, 16u, 16u,
    16u, 16u, 2u, 2u, 15u, 15u, 3u, 3u, 3u, 3u, 14u, 14u,
    14u, 14u, 14u, 14u, 14u, 14u, 4u, 4u, 13u, 13u, 5u, 5u,
    8u, 8u, 8u, 8u, 8u, 8u, 8u, 8u, 8u, 8u, 8u, 8u,
    4u, 4u, 4u, 4u, 9u, 9u, 9u, 9u, 3u, 3u, 3u, 3u,
    3u, 3u, 3u, 3u, 10u, 10u, 10u, 10u, 2u, 2u, 2u, 2u,
    2u, 2u, 2u, 2u, 2u, 2u, 5u, 5u, 5u, 5u, 5u, 5u,
    5u, 5u, 8u, 8u, 0u, 0u, 0u, 0u, 0u, 0u, 6u, 6u,
    9u, 9u, 9u, 9u, 9u, 9u, 5u, 5u, 7u, 7u, 7u, 7u,
    7u, 7u, 7u, 7u, 13u, 13u, 11u, 11u, 14u, 14u, 18u, 18u,
    18u, 18u, 18u, 18u, 18u, 18u, 18u, 18u, 18u, 18u, 15u, 15u,
    15u, 15u, 19u, 19u, 19u, 19u, 19u, 19u, 19u, 19u, 19u, 19u,
    19u, 19u, 16u, 16u, 16u, 16u, 20u, 20u, 20u, 20u, 20u, 20u,
    20u, 20u, 20u, 20u, 20u, 20u, 20u, 20u, 17u, 17u, 17u, 17u,
    21u, 21u, 21u, 21u, 21u, 21u, 21u, 21u, 21u, 21u, 21u, 21u,
    18u, 18u, 22u, 22u, 22u, 22u, 22u, 22u, 22u, 22u, 22u, 22u,
    19u, 19u, 19u, 19u, 20u, 20u, 20u, 20u, 23u, 23u, 23u, 23u,
    23u, 23u, 23u, 23u, 23u, 23u, 18u, 18u, 13u, 13u, 6u, 6u,
    6u, 6u, 6u, 6u, 6u, 6u, 6u, 6u, 6u, 6u, 6u, 6u,
    6u, 6u, 6u, 6u, 11u, 11u, 11u, 11u, 1u, 1u, 12u, 12u,
    12u, 12u, 6u, 6u, 10u, 10u, 10u, 10u, 10u, 10u, 10u, 10u,
    10u, 10u, 7u, 7u, 7u, 7u, 4u, 4u, 12u, 12u, 12u, 12u,
    14u, 14u, 2u, 2u
};

static const uint16_t constellation_compact_led_u16[268] = {
    0u, 0u, 0u, 0u, 38697u, 26838u, 0u, 0u, 0u, 0u, 44087u, 36541u,
    28994u, 21448u, 0u, 0u, 38697u, 26838u, 0u, 0u, 0u, 0u, 50211u, 45227u,
    40243u, 35259u, 30276u, 25292u, 20308u, 15324u, 0u, 0u, 26838u, 38697u, 0u, 0u,
    11751u, 16421u, 21091u, 25762u, 30432u, 35103u, 39773u, 44444u, 49114u, 53784u, 0u, 0u,
    45011u, 36849u, 28686u, 20524u, 0u, 0u, 0u, 0u, 13770u, 19198u, 24626u, 30054u,
    35481u, 40909u, 46337u, 51765u, 0u, 0u, 0u, 0u, 53253u, 48701u, 44148u, 39596u,
    35044u, 30491u, 25939u, 21387u, 16834u, 12282u, 52288u, 46711u, 41133u, 35556u, 29979u, 24402u,
    18824u, 13247u, 0u, 0u, 17501u, 23608u, 29714u, 35821u, 41927u, 48034u, 0u, 0u,
    48885u, 42438u, 35991u, 29544u, 23097u, 16650u, 0u, 0u, 50846u, 45681u, 40515u, 35350u,
    30185u, 25020u, 19854u, 14689u, 0u, 0u, 26838u, 38697u, 0u, 0u, 10975u, 14937u,
    18899u, 22862u, 26824u, 30786u, 34749u, 38711u, 42673u, 46636u, 50598u, 54560u, 0u, 0u,
    0u, 0u, 11586u, 15437u, 19288u, 23140u, 26991u, 30842u, 34693u, 38544u, 42395u, 46247u,
    50098u, 53949u, 0u, 0u, 0u, 0u, 9876u, 13398u, 16920u, 20441u, 23963u, 27485u,
    31007u, 34528u, 38050u, 41572u, 45094u, 48615u, 52137u, 55659u, 0u, 0u, 0u, 0u,
    11823u, 15631u, 19439u, 23247u, 27055u, 30863u, 34672u, 38480u, 42288u, 46096u, 49904u, 53712u,
    0u, 0u, 13186u, 17538u, 21889u, 26240u, 30592u, 34943u, 39295u, 43646u, 47997u, 52349u,
    0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 51909u, 47656u, 43402u, 39148u,
    34894u, 30641u, 26387u, 22133u, 17879u, 13626u, 0u, 0u, 0u, 0u, 58212u, 55219u,
    52225u, 49232u, 46238u, 43245u, 40251u, 37258u, 34264u, 31271u, 28277u, 25284u, 22290u, 19297u,
    16303u, 13310u, 10316u, 7323u, 0u, 0u, 0u, 0u, 37890u, 27645u, 0u, 0u,
    0u, 0u, 0u, 0u, 13079u, 17454u, 21829u, 26205u, 30580u, 34955u, 39330u, 43706u,
    48081u, 52456u, 0u, 0u, 0u, 0u, 0u, 0u, 45277u, 36937u, 28598u, 20258u,
    0u, 0u, 0u, 0u
};

static const uint32_t constellation_compact_star_hip[21] = {
    95168u, 94820u, 93683u, 93085u, 92855u, 92041u, 90496u, 89341u, 89931u, 88635u, 87072u, 90185u,
    89642u, 93506u, 93864u, 96406u, 98688u, 98412u, 98032u, 95347u, 95294u
};

static const int16_t constellation_compact_star_x_dm[21] = {
    793, 1056, 1451, 1612, 1881, 2153, 2526, 2700, 2850, 3243, 3602, 2954,
    3162, 1864, 1662, 838, 398, 896, 1404, 1913, 2168
};

static const int16_t constellation_compact_star_y_dm[21] = {
    621, 708, 887, 662, 1261, 1212, 867, 138, 1295, 1214, 728, 1873,
    2116, 1776, 1587, 1653, 2382, 3168, 3862, 3307, 3758
};

static const int16_t constellation_compact_star_mag_centi[21] = {
    392, 488, 376, 352, 205, 317, 282, 384, 272, 298, 453, 179,
    310, 260, 332, 564, 443, 437, 412, 396, 427
};

static const uint16_t constellation_compact_star_led_offsets[21] = {
    0u, 4u, 8u, 12u, 16u, 20u, 24u, 28u, 32u, 36u, 40u, 44u,
    48u, 52u, 56u, 60u, 64u, 68u, 72u, 76u, 80u
};

static const uint16_t constellation_compact_star_led_counts[21] = {
    4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u,
    4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u, 4u
};

static const uint16_t constellation_compact_star_led_indices[84] = {
    0u, 1u, 2u, 3u, 6u, 7u, 8u, 9u, 14u, 15u, 266u, 267u,
    18u, 19u, 20u, 21u, 30u, 31u, 258u, 259u, 34u, 35u, 102u, 103u,
    94u, 95u, 242u, 243u, 254u, 255u, 256u, 257u, 46u, 47u, 86u, 87u,
    52u, 53u, 54u, 55u, 64u, 65u, 66u, 67u, 232u, 233u, 234u, 235u,
    238u, 239u, 240u, 241u, 112u, 113u, 212u, 213u, 116u, 117u, 264u, 265u,
    130u, 131u, 132u, 133u, 146u, 147u, 148u, 149u, 164u, 165u, 166u, 167u,
    180u, 181u, 210u, 211u, 192u, 193u, 194u, 195u, 196u, 197u, 198u, 199u
};

static const uint16_t constellation_compact_edge_start_star[24] = {
    8u, 12u, 11u, 9u, 9u, 8u, 11u, 13u, 5u, 5u, 6u, 13u,
    14u, 4u, 4u, 3u, 2u, 1u, 14u, 15u, 16u, 17u, 18u, 18u
};

static const uint16_t constellation_compact_edge_end_star[24] = {
    6u, 11u, 9u, 10u, 8u, 11u, 13u, 5u, 8u, 6u, 7u, 14u,
    4u, 5u, 3u, 2u, 1u, 0u, 15u, 16u, 17u, 18u, 19u, 20u
};

static const uint16_t constellation_compact_edge_length_dm[24] = {
    537u, 320u, 720u, 604u, 401u, 588u, 1095u, 634u, 702u, 508u, 749u, 276u,
    393u, 276u, 657u, 276u, 434u, 276u, 827u, 851u, 930u, 860u, 753u, 770u
};

static const uint16_t constellation_compact_edge_led_offsets[24] = {
    0u, 6u, 8u, 18u, 26u, 30u, 38u, 56u, 64u, 74u, 80u, 90u,
    92u, 96u, 98u, 106u, 108u, 112u, 114u, 126u, 138u, 152u, 164u, 174u
};

static const uint16_t constellation_compact_edge_led_counts[24] = {
    6u, 2u, 10u, 8u, 4u, 8u, 18u, 8u, 10u, 6u, 10u, 2u,
    4u, 2u, 8u, 2u, 4u, 2u, 12u, 12u, 14u, 12u, 10u, 10u
};

static const uint16_t constellation_compact_edge_led_indices[184] = {
    88u, 89u, 90u, 91u, 92u, 93u, 236u, 237u, 68u, 69u, 70u, 71u,
    72u, 73u, 74u, 75u, 76u, 77u, 56u, 57u, 58u, 59u, 60u, 61u,
    62u, 63u, 48u, 49u, 50u, 51u, 78u, 79u, 80u, 81u, 82u, 83u,
    84u, 85u, 214u, 215u, 216u, 217u, 218u, 219u, 220u, 221u, 222u, 223u,
    224u, 225u, 226u, 227u, 228u, 229u, 230u, 231u, 104u, 105u, 106u, 107u,
    108u, 109u, 110u, 111u, 36u, 37u, 38u, 39u, 40u, 41u, 42u, 43u,
    44u, 45u, 96u, 97u, 98u, 99u, 100u, 101u, 244u, 245u, 246u, 247u,
    248u, 249u, 250u, 251u, 252u, 253u, 114u, 115u, 260u, 261u, 262u, 263u,
    32u, 33u, 22u, 23u, 24u, 25u, 26u, 27u, 28u, 29u, 16u, 17u,
    10u, 11u, 12u, 13u, 4u, 5u, 118u, 119u, 120u, 121u, 122u, 123u,
    124u, 125u, 126u, 127u, 128u, 129u, 134u, 135u, 136u, 137u, 138u, 139u,
    140u, 141u, 142u, 143u, 144u, 145u, 150u, 151u, 152u, 153u, 154u, 155u,
    156u, 157u, 158u, 159u, 160u, 161u, 162u, 163u, 168u, 169u, 170u, 171u,
    172u, 173u, 174u, 175u, 176u, 177u, 178u, 179u, 182u, 183u, 184u, 185u,
    186u, 187u, 188u, 189u, 190u, 191u, 200u, 201u, 202u, 203u, 204u, 205u,
    206u, 207u, 208u, 209u
};

static const uint16_t constellation_compact_adjacency_offsets[22] = {
    0u, 1u, 3u, 5u, 7u, 10u, 14u, 17u, 18u, 22u, 25u, 26u,
    30u, 31u, 34u, 37u, 39u, 41u, 43u, 46u, 47u, 48u
};

static const uint16_t constellation_compact_adjacency_neighbor_star[48] = {
    1u, 2u, 0u, 3u, 1u, 4u, 2u, 14u, 5u, 3u, 13u, 8u,
    6u, 4u, 8u, 5u, 7u, 6u, 6u, 9u, 11u, 5u, 11u, 10u,
    8u, 9u, 12u, 9u, 8u, 13u, 11u, 11u, 5u, 14u, 13u, 4u,
    15u, 14u, 16u, 15u, 17u, 16u, 18u, 17u, 19u, 20u, 18u, 18u
};

static const uint16_t constellation_compact_adjacency_edge_index[48] = {
    17u, 16u, 17u, 15u, 16u, 14u, 15u, 12u, 13u, 14u, 7u, 8u,
    9u, 13u, 0u, 9u, 10u, 10u, 0u, 4u, 5u, 8u, 2u, 3u,
    4u, 3u, 1u, 2u, 5u, 6u, 1u, 6u, 7u, 11u, 11u, 12u,
    18u, 18u, 19u, 19u, 20u, 20u, 21u, 21u, 22u, 23u, 22u, 23u
};

#endif /* CONSTELLATION_LAMP_COMPACT_SCENE_DATA_H */
