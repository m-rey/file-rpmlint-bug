# About
This programm pulls rpmlint errors and warnings from  [build-check-statistics](https://github.com/openSUSE/build-check-statistics)
and adds them as reports to a bugzilla instance using a two step process.

# WIP
THIS PROJECT IS WIP

The code that /should/ create the bugzilla bug reports, is commented out. Code that mocks that functionality is marked with "TODO: delete this" or similar.

# Usage
1. `python filerpmlintbug.py --pull -c config.ini data.json`
2. `python filerpmlintbug.py --push -c config.ini data.json`

In the first step, all necessary information to create the bug reports is stored in `data.json` using the following format:

```
.         
├── $rmplint-error-1
│   └── bug_config 
│   │   └── assigned_to
│   │   │   └── $assigned_to
│   │   └── cc
│   │   │   └── $cc1
│   │   │   └── $cc2
│   │   │   ︙
│   │   └── product
│   │   │   └── $product
│   │   └── component
│   │   │   └── $component
│   │   └── version
│   │   │   └── $version
│   │   └── summary
│   │   │   └── $summary
│   │   └── description
│   │   │   └── $description
│   │   └── id
│   │      └── $id
│   └── packages
│       └── $package-1
│       │   └── bug_config
│       │   │   └── assigned_to
│       │   │   │   └── $assigned_to
│       │   │   └── product
│       │   │   │   └── $product
│       │   └── component
│       │   │   └── $component
│       │   └── version
│       │   │   └── $version
│       │   └── summary
│       │   │   └── $summary
│       │   └── description
│       │   │   └── $description
│       │   └── id
│       │      └── $id
︙      ︙        
│   
├── rmplint-error-2
︙      ︙ 
```
In the second step, `data.json` is used to create bugzilla bug reports. The corresponding bug id is added back to data.json`.
