# JSON-столбцы

## `car.specs`

```jsonc
{
  "engine": {
    "layout": "V8",            // I4, I6, V6, V8, V10, V12, F6, F12
    "cylinders": 8,
    "displacement_l": 2.4,
    "turbo": false,
    "hybrid": { "ers_kw": 60 } // может не быть
  },
  "aero": {                    // может не быть
    "downforce": "low",        // low, medium, high
    "drs": true                // может не быть
  },
  "tyres": ["soft", "medium", "hard", "intermediate", "wet"], // или ["dry", "wet"], ["slick"]
  "sponsors": [                // может не быть, может быть []
    { "name": "Pirelli", "share": 0.25 },
    { "name": "Castrol", "share": 0.14 }
  ],
  "top_speed_kmh": 327,
  "homologated": true
}
```

## `race_entry.pit_stops`

```jsonc
[                              // может быть []
  { "lap": 4,  "duration_s": 12.6, "tyre": "soft" },  // tyre: soft, medium, hard, intermediate, wet
  { "lap": 31, "duration_s": 15.5, "tyre": "hard" },
  { "lap": 70, "duration_s": 34.3, "tyre": "wet" }
]
```
