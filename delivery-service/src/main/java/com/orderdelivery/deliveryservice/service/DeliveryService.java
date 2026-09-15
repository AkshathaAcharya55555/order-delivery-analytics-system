package com.orderdelivery.deliveryservice.service;

import com.orderdelivery.deliveryservice.entity.Delivery;
import com.orderdelivery.deliveryservice.entity.Location;
import com.orderdelivery.deliveryservice.entity.Order;
import com.orderdelivery.deliveryservice.entity.OrderStatusHistory;
import com.orderdelivery.deliveryservice.entity.Rider;
import com.orderdelivery.deliveryservice.event.EventPublisher;
import com.orderdelivery.deliveryservice.exception.InvalidStateException;
import com.orderdelivery.deliveryservice.exception.NoAvailableRiderException;
import com.orderdelivery.deliveryservice.exception.ResourceNotFoundException;
import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import com.orderdelivery.deliveryservice.repository.DeliveryRepository;
import com.orderdelivery.deliveryservice.repository.LocationRepository;
import com.orderdelivery.deliveryservice.repository.OrderRepository;
import com.orderdelivery.deliveryservice.repository.OrderStatusHistoryRepository;
import com.orderdelivery.deliveryservice.repository.RiderRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.function.ToLongFunction;
import java.util.stream.Collectors;

@Service
public class DeliveryService {

    private static final EnumSet<DeliveryStatus> ACTIVE_DELIVERY_STATUSES =
            EnumSet.of(DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP, DeliveryStatus.OUT_FOR_DELIVERY);

    private final DeliveryRepository deliveryRepository;
    private final RiderRepository riderRepository;
    private final OrderRepository orderRepository;
    private final LocationRepository locationRepository;
    private final OrderStatusHistoryRepository historyRepository;
    private final RiderMatcher riderMatcher;
    private final EventPublisher eventPublisher;

    public DeliveryService(DeliveryRepository deliveryRepository, RiderRepository riderRepository,
                            OrderRepository orderRepository, LocationRepository locationRepository,
                            OrderStatusHistoryRepository historyRepository, RiderMatcher riderMatcher,
                            EventPublisher eventPublisher) {
        this.deliveryRepository = deliveryRepository;
        this.riderRepository = riderRepository;
        this.orderRepository = orderRepository;
        this.locationRepository = locationRepository;
        this.historyRepository = historyRepository;
        this.riderMatcher = riderMatcher;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public Delivery assignRider(Long orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));

        if (order.getStatus().isTerminal()) {
            throw new InvalidStateException("Order " + orderId + " is already " + order.getStatus() + "; cannot assign a rider");
        }
        if (deliveryRepository.findByOrderId(orderId).isPresent()) {
            throw new InvalidStateException("Order " + orderId + " already has a rider assigned");
        }

        Location location = locationRepository.findById(order.getDeliveryLocationId())
                .orElseThrow(() -> new ResourceNotFoundException("Location not found: " + order.getDeliveryLocationId()));
        if (location.getLatitude() == null || location.getLongitude() == null) {
            throw new InvalidStateException("Delivery location " + location.getLocationId() + " has no coordinates");
        }

        List<Rider> candidates = riderRepository.findByCityAndActiveTrueAndAvailableTrue(location.getCity());
        if (candidates.isEmpty()) {
            throw new NoAvailableRiderException("No available rider in city: " + location.getCity());
        }

        // One batched query for every candidate's current workload, instead of
        // one COUNT query per candidate (the latter took several minutes for
        // a real ~300-rider city under Docker - see docs/FINAL_AUDIT.md).
        List<Long> candidateIds = candidates.stream().map(Rider::getRiderId).toList();
        Map<Long, Long> workloadByRiderId = deliveryRepository
                .countActiveDeliveriesGroupedByRider(candidateIds, ACTIVE_DELIVERY_STATUSES)
                .stream()
                .collect(Collectors.toMap(
                        DeliveryRepository.RiderWorkloadCount::getRiderId,
                        DeliveryRepository.RiderWorkloadCount::getActiveCount));
        ToLongFunction<Rider> workloadOf = rider -> workloadByRiderId.getOrDefault(rider.getRiderId(), 0L);

        var best = riderMatcher.selectBestRider(
                candidates,
                location.getLatitude().doubleValue(),
                location.getLongitude().doubleValue(),
                workloadOf
        ).orElseThrow(() -> new NoAvailableRiderException("No available rider in city: " + location.getCity()));

        LocalDateTime now = LocalDateTime.now();
        Delivery delivery = new Delivery(orderId, best.rider().getRiderId(), now, DeliveryStatus.ASSIGNED,
                BigDecimal.valueOf(best.distanceKm()).setScale(2, java.math.RoundingMode.HALF_UP));
        Delivery saved = deliveryRepository.save(delivery);

        order.setRiderId(best.rider().getRiderId());
        order.setStatus(com.orderdelivery.deliveryservice.model.OrderStatus.RIDER_ASSIGNED);
        orderRepository.save(order);
        historyRepository.save(new OrderStatusHistory(orderId,
                com.orderdelivery.deliveryservice.model.OrderStatus.RIDER_ASSIGNED, now));

        eventPublisher.publishRiderAssigned(orderId, Map.of(
                "rider_id", best.rider().getRiderId(),
                "distance_km", best.distanceKm()));

        return saved;
    }

    @Transactional
    public Delivery updateStatus(Long orderId, DeliveryStatus newStatus) {
        Delivery delivery = deliveryRepository.findByOrderId(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("No delivery found for order: " + orderId));

        if (!delivery.getDeliveryStatus().canTransitionTo(newStatus)) {
            throw new InvalidStateException(
                    "Delivery for order " + orderId + " cannot move from " + delivery.getDeliveryStatus() + " to " + newStatus);
        }

        LocalDateTime now = LocalDateTime.now();
        delivery.setDeliveryStatus(newStatus);
        if (newStatus == DeliveryStatus.PICKED_UP) {
            delivery.setPickedUpAt(now);
        } else if (newStatus == DeliveryStatus.DELIVERED) {
            delivery.setDeliveredAt(now);
        }
        Delivery saved = deliveryRepository.save(delivery);

        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
        order.setStatus(newStatus.toOrderStatus());
        orderRepository.save(order);
        historyRepository.save(new OrderStatusHistory(orderId, newStatus.toOrderStatus(), now));

        publishForStatus(orderId, newStatus, delivery.getRiderId());

        return saved;
    }

    private void publishForStatus(Long orderId, DeliveryStatus newStatus, Long riderId) {
        Map<String, Object> payload = Map.of("rider_id", riderId);
        switch (newStatus) {
            case OUT_FOR_DELIVERY -> eventPublisher.publishDeliveryStarted(orderId, payload);
            case DELIVERED -> eventPublisher.publishDeliveryCompleted(orderId, payload);
            case FAILED -> eventPublisher.publishDeliveryFailed(orderId, payload);
            default -> { /* PICKED_UP has no dedicated event in the required 7-event set */ }
        }
    }

    @Transactional(readOnly = true)
    public Delivery getByOrderId(Long orderId) {
        return deliveryRepository.findByOrderId(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("No delivery found for order: " + orderId));
    }
}
