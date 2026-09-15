package com.orderdelivery.deliveryservice.dto;

import com.orderdelivery.deliveryservice.entity.Rider;
import java.math.BigDecimal;

public class RiderResponse {

    private final Long riderId;
    private final String firstName;
    private final String lastName;
    private final String vehicleType;
    private final String city;
    private final BigDecimal rating;
    private final boolean active;
    private final boolean available;
    private final BigDecimal currentLatitude;
    private final BigDecimal currentLongitude;

    public RiderResponse(Long riderId, String firstName, String lastName, String vehicleType, String city,
                          BigDecimal rating, boolean active, boolean available,
                          BigDecimal currentLatitude, BigDecimal currentLongitude) {
        this.riderId = riderId;
        this.firstName = firstName;
        this.lastName = lastName;
        this.vehicleType = vehicleType;
        this.city = city;
        this.rating = rating;
        this.active = active;
        this.available = available;
        this.currentLatitude = currentLatitude;
        this.currentLongitude = currentLongitude;
    }

    public static RiderResponse from(Rider r) {
        return new RiderResponse(r.getRiderId(), r.getFirstName(), r.getLastName(), r.getVehicleType(),
                r.getCity(), r.getRating(), r.isActive(), r.isAvailable(),
                r.getCurrentLatitude(), r.getCurrentLongitude());
    }

    public Long getRiderId() {
        return riderId;
    }

    public String getFirstName() {
        return firstName;
    }

    public String getLastName() {
        return lastName;
    }

    public String getVehicleType() {
        return vehicleType;
    }

    public String getCity() {
        return city;
    }

    public BigDecimal getRating() {
        return rating;
    }

    public boolean isActive() {
        return active;
    }

    public boolean isAvailable() {
        return available;
    }

    public BigDecimal getCurrentLatitude() {
        return currentLatitude;
    }

    public BigDecimal getCurrentLongitude() {
        return currentLongitude;
    }
}
