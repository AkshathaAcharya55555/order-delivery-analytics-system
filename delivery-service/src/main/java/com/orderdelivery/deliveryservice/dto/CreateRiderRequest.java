package com.orderdelivery.deliveryservice.dto;

import jakarta.validation.constraints.*;
import java.math.BigDecimal;

public class CreateRiderRequest {

    @NotBlank
    private String firstName;

    @NotBlank
    private String lastName;

    @NotBlank
    private String phone;

    @NotNull
    @Pattern(regexp = "bike|scooter|car|bicycle")
    private String vehicleType;

    @NotBlank
    private String city;

    @DecimalMin(value = "0.0")
    @DecimalMax(value = "5.0")
    private BigDecimal rating;

    /** Optional last-known GPS position; falls back to the city centroid when omitted. */
    private BigDecimal currentLatitude;
    private BigDecimal currentLongitude;

    public String getFirstName() {
        return firstName;
    }

    public void setFirstName(String firstName) {
        this.firstName = firstName;
    }

    public String getLastName() {
        return lastName;
    }

    public void setLastName(String lastName) {
        this.lastName = lastName;
    }

    public String getPhone() {
        return phone;
    }

    public void setPhone(String phone) {
        this.phone = phone;
    }

    public String getVehicleType() {
        return vehicleType;
    }

    public void setVehicleType(String vehicleType) {
        this.vehicleType = vehicleType;
    }

    public String getCity() {
        return city;
    }

    public void setCity(String city) {
        this.city = city;
    }

    public BigDecimal getRating() {
        return rating;
    }

    public void setRating(BigDecimal rating) {
        this.rating = rating;
    }

    public BigDecimal getCurrentLatitude() {
        return currentLatitude;
    }

    public void setCurrentLatitude(BigDecimal currentLatitude) {
        this.currentLatitude = currentLatitude;
    }

    public BigDecimal getCurrentLongitude() {
        return currentLongitude;
    }

    public void setCurrentLongitude(BigDecimal currentLongitude) {
        this.currentLongitude = currentLongitude;
    }
}
