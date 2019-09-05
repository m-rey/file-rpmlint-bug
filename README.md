# About
This programm pulls rpmlint errors and warnings from  [build-check-statistics](https://github.com/openSUSE/build-check-statistics)
and adds them to a bugzilla instace.

# Usage
1. `python filerpmlintbug.py -v --pull -c config.ini data.json`
2. `python filerpmlintbug.py -v --push -c config.ini data.json`

In the first step, the rpmlint error/warning information is stored in data.json using the following format:

```
.         
├── $rmplint-error-1
│   └── bug_config 
│   │   └── assigned_to
│   │   │   └── $assigned_to
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
'       '        
│   
├── rmplint-error-2
.
``
