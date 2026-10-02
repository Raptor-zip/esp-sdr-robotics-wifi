idf_component_register(SRCS "controller.c" INCLUDE_DIRS "." REQUIRES esp_wifi esp_event esp_netif nvs_flash esp_driver_uart esp_timer lwip)
