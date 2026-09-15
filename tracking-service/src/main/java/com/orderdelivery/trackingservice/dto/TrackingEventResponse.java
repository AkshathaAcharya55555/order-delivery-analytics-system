package com.orderdelivery.trackingservice.dto;

import com.orderdelivery.trackingservice.entity.OrderStatusHistory;
import java.time.LocalDateTime;

public class TrackingEventResponse {

    private final String status;
    private final LocalDateTime changedAt;

    public TrackingEventResponse(String status, LocalDateTime changedAt) {
        this.status = status;
        this.changedAt = changedAt;
    }

    public static TrackingEventResponse from(OrderStatusHistory h) {
        return new TrackingEventResponse(h.getStatus().name(), h.getChangedAt());
    }

    public String getStatus() {
        return status;
    }

    public LocalDateTime getChangedAt() {
        return changedAt;
    }
}
