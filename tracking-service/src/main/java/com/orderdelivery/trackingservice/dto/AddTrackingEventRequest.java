package com.orderdelivery.trackingservice.dto;

import com.orderdelivery.trackingservice.model.OrderStatus;
import jakarta.validation.constraints.NotNull;

public class AddTrackingEventRequest {

    @NotNull
    private OrderStatus status;

    public OrderStatus getStatus() {
        return status;
    }

    public void setStatus(OrderStatus status) {
        this.status = status;
    }
}
