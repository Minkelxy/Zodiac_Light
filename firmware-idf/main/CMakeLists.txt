set(clp_scene_includes "." "../../firmware/include")
if(DEFINED CLP_GENERATED_DIR)
    file(TO_CMAKE_PATH "${CLP_GENERATED_DIR}" clp_generated_normalized)
    list(PREPEND clp_scene_includes "${clp_generated_normalized}")
endif()
idf_component_register(SRCS "main.cpp" "ws2812_encoder.c" "native_effects.cpp"
                       INCLUDE_DIRS ${clp_scene_includes}
                       REQUIRES driver esp_timer)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_14)
