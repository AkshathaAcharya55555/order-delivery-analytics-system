package com.orderdelivery.deliveryservice.entity;

import com.orderdelivery.deliveryservice.model.OrderStatus;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Trimmed view of the orders table (owned by database/schema.sql, shared
 * with order-service). This service only needs to read order/customer
 * location context and write rider_id + status during delivery handling.
 */
@Entity
@Table(name = "orders")
public class Order {

    @Id
    @Column(name = "order_id")
    private Long orderId;

    @Column(name = "customer_id", nullable = false)
    private Long customerId;

    @Column(name = "delivery_location_id", nullable = false)
    private Long deliveryLocationId;

    @Column(name = "rider_id")
    private Long riderId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private OrderStatus status;

    @Column(name = "order_placed_at", nullable = false, insertable = false, updatable = false)
    private LocalDateTime orderPlacedAt;

    @Column(name = "total_amount", nullable = false, precision = 10, scale = 2, insertable = false, updatable = false)
    private BigDecimal totalAmount;

    @Column(name = "payment_method", nullable = false, length = 30, insertable = false, updatable = false)
    private String paymentMethod;

    protected Order() {
    }

    public Long getOrderId() {
        return orderId;
    }

    public Long getCustomerId() {
        return customerId;
    }

    public Long getDeliveryLocationId() {
        return deliveryLocationId;
    }

    public Long getRiderId() {
        return riderId;
    }

    public void setRiderId(Long riderId) {
        this.riderId = riderId;
    }

    public OrderStatus getStatus() {
        return status;
    }

    public void setStatus(OrderStatus status) {
        this.status = status;
    }

    public LocalDateTime getOrderPlacedAt() {
        return orderPlacedAt;
    }

    public BigDecimal getTotalAmount() {
        return totalAmount;
    }

    public String getPaymentMethod() {
        return paymentMethod;
    }
}
