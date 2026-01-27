# autoroad
> trajectory optimization for your mit degree

# TLDR
- pick classes you *want* to take
- pick degrees and concentrations you want
- let autoroad fill out the rest

## How do I use this?
Try it out at [autoroad.auriium.xyz](https://autoroad.auriium.xyz)

## Why does this exist?
If you want your degree to not kill you or make you bald, you have to consider and exploit:
- classes have different amounts of units
- classes have different amounts of hours (you want less of these)
- classes have different ratings and enrollments (do not take a class rated under 5)

As both a fake mechanical engineer and a fake CS major, trying to solve this convoluted mess by hand for *two different degrees* was wasting time. So, I sat down and built autoroad!

## How does it work?
See [TECHNICAL.md](TECHNICAL.md) for details on the optimization system.

## What next?
- Autoroad's integer programming design could be expanded to use a more generic api than fireroad, allowing other schools to integrate
- Autoroad's remote c++ solver pool design can allow for other types of integer programming problems to be shipped off to the worker pool

## Credits
- auriium2
- ricardo ochoa for telling me to add category weighting
- reactflow, for their great graph library
- SIPB, for making and maintaining the fireroad api and the original Courseroad!
