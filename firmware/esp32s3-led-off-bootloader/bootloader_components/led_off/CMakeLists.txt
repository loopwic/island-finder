idf_component_register(SRCS "led_off.c")

# The normal bootloader hooks are weak symbols. Referencing this symbol from
# led_off.c forces the component archive into the second-stage bootloader.
