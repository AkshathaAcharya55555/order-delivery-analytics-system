package com.orderdelivery.trackingservice.dto;

import java.util.List;

public class TrackingResponse {

    private final Long orderId;
    private final String currentStatus;
    private final List<TrackingEventResponse> history;

    public TrackingResponse(Long orderId, String currentStatus, List<TrackingEventResponse> history) {
        this.orderId = orderId;
        this.currentStatus = currentStatus;
        this.history = history;
    }

    public Long getOrderId() {
        return orderId;
    }

    public String getCurrentStatus() {
        return currentStatus;
    }

    public List<TrackingEventResponse> getHistory() {
        return history;
    }
}
