package com.orderdelivery.orderservice.entity;

import com.orderdelivery.orderservice.model.OrderStatus;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "orders")
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
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

    @Column(name = "order_placed_at", nullable = false)
    private LocalDateTime orderPlacedAt;

    @Column(name = "total_amount", nullable = false, precision = 10, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "payment_method", nullable = false, length = 30)
    private String paymentMethod;

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    private List<OrderItem> items = new ArrayList<>();

    protected Order() {
    }

    public Order(Long customerId, Long deliveryLocationId, OrderStatus status,
                 LocalDateTime orderPlacedAt, BigDecimal totalAmount, String paymentMethod) {
        this.customerId = customerId;
        this.deliveryLocationId = deliveryLocationId;
        this.status = status;
        this.orderPlacedAt = orderPlacedAt;
        this.totalAmount = totalAmount;
        this.paymentMethod = paymentMethod;
    }

    public void addItem(OrderItem item) {
        items.add(item);
        item.setOrder(this);
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

    public void setTotalAmount(BigDecimal totalAmount) {
        this.totalAmount = totalAmount;
    }

    public String getPaymentMethod() {
        return paymentMethod;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public List<OrderItem> getItems() {
        return items;
    }
}
