package com.orderdelivery.deliveryservice.dto;

public class RiderAvailabilityResponse {

    private final Long riderId;
    private final boolean available;

    public RiderAvailabilityResponse(Long riderId, boolean available) {
        this.riderId = riderId;
        this.available = available;
    }

    public Long getRiderId() {
        return riderId;
    }

    public boolean isAvailable() {
        return available;
    }
}
